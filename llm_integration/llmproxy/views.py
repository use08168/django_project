# 04_project/llm_integration/llmproxy/views.py
import os
import html
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import boto3
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .models import Conversation, Message
from .utils.llm_client import LLMClient
from .utils.storage import upload_file
from .utils.pdf_to_md import pdf_bytes_to_markdown


def _ensure_session_key(request: HttpRequest) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def landing(request: HttpRequest):
    return render(request, "main.html", {"is_authenticated": request.user.is_authenticated})


def chat_page(request: HttpRequest):
    if not request.user.is_authenticated:
        return redirect("/llm/")
    return render(request, "chat.html")


def _presign_if_s3(url: str, expires: int = 3600) -> str:
    """
    - 이미 presigned(쿼리에 X-Amz-Algorithm/Signature)면 **그대로 반환** (이중 서명 금지)
    - 비서명 URL이면 key를 추출해 **한글/공백 unquote** 후 presign
    - 실패 시 원본 URL 반환
    """
    if not url:
        return url

    u = urlparse(url)
    q = parse_qs(u.query)
    if "X-Amz-Signature" in q or "X-Amz-Algorithm" in q:
        return url  # already presigned

    bucket = getattr(settings, "AWS_S3_BUCKET", None) or getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    region = getattr(settings, "AWS_S3_REGION_NAME", None) or getattr(settings, "AWS_REGION", None) or os.getenv("AWS_REGION")
    if not bucket or not region:
        return url

    # key 추출 (virtual-hosted / path-style 둘 다 시도)
    key_candidate = None
    try:
        if u.netloc.startswith(bucket + ".") and u.path:
            # https://{bucket}.s3.{region}.amazonaws.com/{key}
            key_candidate = u.path.lstrip("/")
        else:
            # https://s3.{region}.amazonaws.com/{bucket}/{key}
            parts = u.path.split("/")
            if len(parts) >= 3 and parts[1] == bucket:
                key_candidate = "/".join(parts[2:])
        if not key_candidate:
            return url

        # 퍼센트 인코딩 복원 (한글/공백!)
        key = unquote(key_candidate)

        s3 = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", getattr(settings, "AWS_ACCESS_KEY_ID", None)),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", getattr(settings, "AWS_SECRET_ACCESS_KEY", None)),
            # 필요하면 서명버전 강제:
            # config=Config(signature_version="s3v4"),
        )
        signed = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
        return signed
    except Exception:
        return url


@login_required
def chat_history(request: HttpRequest):
    session_key = _ensure_session_key(request)
    conv_id = request.GET.get("conversation_id")

    qs = Conversation.objects.filter(user=request.user)
    if conv_id:
        try:
            conv = qs.get(pk=conv_id, user=request.user)
        except Conversation.DoesNotExist:
            return JsonResponse({"ok": False, "error": "conversation not found"}, status=404)
    else:
        conv = qs.order_by("-updated_at", "-id").first()
        if not conv:
            conv = Conversation.objects.create(user=request.user, session_key=session_key, title="New Chat")

    last50 = list(conv.messages.all().order_by("-id")[:50])
    last50.reverse()
    items = [
        {"id": m.id, "role": m.role, "content": m.content, "file_url": m.file_url, "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S")}
        for m in last50
    ]

    # 화면 표시용 presigned URL (DB에는 비서명 저장)
    presigned = _presign_if_s3(conv.uploaded_pdf_url) if conv.uploaded_pdf_url else ""

    return JsonResponse({
        "ok": True,
        "conversation_id": conv.id,
        "title": conv.title,
        "uploaded_pdf_url": presigned,
        "items": items
    })


@require_POST
@login_required
@transaction.atomic
def chat_send(request: HttpRequest):
    session_key = _ensure_session_key(request)
    content = (request.POST.get("message") or "").trim() if hasattr(str, "trim") else (request.POST.get("message") or "").strip()
    conv_id = request.POST.get("conversation_id")

    if not content:
        return JsonResponse({"ok": False, "error": "message is empty"}, status=400)

    # resolve conversation
    if conv_id:
        try:
            conv = Conversation.objects.get(pk=conv_id, user=request.user)
        except Conversation.DoesNotExist:
            return JsonResponse({"ok": False, "error": "conversation not found"}, status=404)
    else:
        conv = Conversation.objects.filter(user=request.user).order_by("-updated_at", "-id").first()
        if not conv:
            conv = Conversation.objects.create(user=request.user, session_key=session_key, title="New Chat")

    # save user message
    Message.objects.create(conversation=conv, role="user", content=content)
    # set title from first question if empty
    if not conv.title:
        conv.title = content[:10]
        conv.save(update_fields=["title", "updated_at"])

    # collect last few messages for context
    history = [
        {"role": m.role, "content": m.content}
        for m in conv.messages.all().order_by("-id")[:10][::-1]
    ]

    client = LLMClient()
    import time
    start = time.time()
    attachments = None
    # RunPod는 내부 인덱스를 쓰지만, 처음 1회 업로드한 PDF의 MD를 system message로 보낼 수 있음
    if conv.uploaded_pdf_url and (not conv.pdf_context_attached) and conv.pdf_context_md:
        attachments = [{"type": "markdown", "content": conv.pdf_context_md, "name": "uploaded.pdf.md"}]

    try:
        result = client.chat(
            messages=history,
            user_id=str(request.user.email or request.user.username),
            session_id=str(conv.id),
            max_tokens=1024,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.05,
            k_internal=6,
            k_external=0,
            attachments=attachments,
        )
        reply = (result.get("answer") or
                 result.get("choices", [{}])[0].get("message", {}).get("content") or
                 "")
    except Exception as e:
        reply = f"LLM error: {e}"
    elapsed_ms = int((time.time() - start) * 1000)

    msg = Message.objects.create(conversation=conv, role="assistant", content=reply)
    if attachments:
        conv.pdf_context_attached = True
        conv.save(update_fields=["pdf_context_attached", "updated_at"])

    return JsonResponse({
        "ok": True,
        "conversation_id": conv.id,
        "item": {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_ms": elapsed_ms,
        },
    })


@require_POST
@login_required
def file_upload(request: HttpRequest):
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"ok": False, "error": "no file"}, status=400)
    if f.size > 10 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "파일 크기 제한(10MB) 초과"}, status=400)

    conv_id = request.POST.get("conversation_id")
    if not conv_id:
        session_key = _ensure_session_key(request)
        conv = Conversation.objects.create(user=request.user, session_key=session_key, title="")
    else:
        try:
            conv = Conversation.objects.get(pk=conv_id, user=request.user)
        except Conversation.DoesNotExist:
            return JsonResponse({"ok": False, "error": "conversation not found"}, status=404)

    if conv.uploaded_pdf_url:
        return JsonResponse({"ok": False, "error": "이미 PDF가 업로드되었습니다."}, status=400)

    # bytes 미리 읽고, 다시 포인터 복귀
    data_bytes = None
    try:
        data_bytes = f.read()
        if hasattr(f, "seek"):
            f.seek(0)
    except Exception:
        data_bytes = None

    # 1) S3 업로드 (DB에는 비서명 URL 저장)
    base_url = upload_file(f, f.name, prefix=f"uploads/{request.user.id}/{conv.id}/")
    base_name = (f.name or "").rsplit("/", 1)[-1]
    title_from_pdf = base_name[:10] if base_name else "새 채팅"
    conv.uploaded_pdf_url = base_url
    conv.title = title_from_pdf

    # 2) PDF→Markdown 추출(있으면)
    try:
        if data_bytes:
            conv.pdf_context_md = pdf_bytes_to_markdown(data_bytes)
            # 인덱싱 성공 전까지는 system 첨부를 계속 쓰고 싶으므로 False 유지
            conv.pdf_context_attached = False
    except Exception:
        pass

    # 3) RunPod 인덱싱 호출 (동일한 user_id / session_id!)
    ingest_ok = False
    try:
        rp_base = getattr(settings, "RUNPOD_API_BASE", "").rstrip("/")
        if rp_base and data_bytes:
            files = {"file": (base_name or "upload.pdf", data_bytes, "application/pdf")}
            data = {
                "user_id": str(request.user.email or request.user.username or request.user.id),
                "session_id": str(conv.id),
                "prefer_openai": "true",
            }
            rp = requests.post(f"{rp_base}/v1/ingest", files=files, data=data, timeout=int(getattr(settings, "RUNPOD_TIMEOUT", 120)))
            if rp.ok:
                j = rp.json()
                ingest_ok = bool(j.get("ok"))
    except Exception:
        ingest_ok = False

    # 인덱싱이 성공했으면 system 첨부는 안 해도 되니 True로
    if ingest_ok:
        conv.pdf_context_attached = True

    conv.save(update_fields=["uploaded_pdf_url", "title", "pdf_context_md", "pdf_context_attached", "updated_at"])

    # 화면에는 presigned URL
    return JsonResponse({"ok": True, "url": _presign_if_s3(conv.uploaded_pdf_url), "conversation_id": conv.id, "title": conv.title})


def _read_policy_file(filename: str) -> str:
    base: Path = settings.BASE_DIR
    p = base / "docs" / filename
    try:
        txt = p.read_text(encoding="utf-8")
        safe = html.escape(txt).replace("\n", "<br>")
        return f"<div class='text-sm leading-relaxed whitespace-normal'>{safe}</div>"
    except Exception as e:
        return f"<div class='text-sm text-red-600'>문서를 불러오지 못했습니다: {html.escape(str(e))}</div>"


def policy_terms(request: HttpRequest):
    return JsonResponse({"ok": True, "html": _read_policy_file("서비스이용약관.txt")})


def policy_privacy(request: HttpRequest):
    return JsonResponse({"ok": True, "html": _read_policy_file("개인정보동의.txt")})


@login_required
def conversations_list(request: HttpRequest):
    _ensure_session_key(request)
    qs = Conversation.objects.filter(user=request.user).order_by("-updated_at", "-id")
    data = [
        {"id": c.id, "title": c.title or "새 채팅", "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M:%S")}
        for c in qs
    ]
    return JsonResponse({"ok": True, "items": data})


@require_POST
@login_required
def conversations_new(request: HttpRequest):
    session_key = _ensure_session_key(request)
    conv = Conversation.objects.create(user=request.user, session_key=session_key, title="새 채팅")
    return JsonResponse({"ok": True, "id": conv.id, "title": conv.title})


@require_POST
@login_required
def conversations_rename(request: HttpRequest):
    conv_id = request.POST.get("id")
    title = (request.POST.get("title") or "").strip()[:255]
    try:
        conv = Conversation.objects.get(pk=conv_id, user=request.user)
    except Conversation.DoesNotExist:
        return JsonResponse({"ok": False, "error": "conversation not found"}, status=404)
    conv.title = title or "새 채팅"
    conv.save(update_fields=["title", "updated_at"])
    return JsonResponse({"ok": True})


@require_POST
@login_required
def conversations_delete(request: HttpRequest):
    conv_id = request.POST.get("id")
    try:
        conv = Conversation.objects.get(pk=conv_id, user=request.user)
    except Conversation.DoesNotExist:
        return JsonResponse({"ok": False, "error": "conversation not found"}, status=404)
    conv.delete()
    return JsonResponse({"ok": True})
