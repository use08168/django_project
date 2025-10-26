# 04_project/llm_integration/llmproxy/utils/storage.py
import os
import uuid
import boto3
from django.conf import settings
from urllib.parse import quote

def _safe_filename(name: str) -> str:
    # 공백 정리
    name = (name or "file").strip()
    # 너무 긴 이름 컷
    if len(name) > 140:
        base, dot, ext = name.rpartition(".")
        name = (base[:120] + ("." + ext if ext else "")) if base else name[:140]
    return name

def upload_file(django_file, original_name: str, prefix: str = "uploads/") -> str:
    """
    S3에 업로드하고 '비서명 URL'을 반환한다.
    presigned URL은 뷰단에서 매요청 생성해 내려준다.
    """
    bucket = getattr(settings, "AWS_S3_BUCKET", "") or getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    region = getattr(settings, "AWS_S3_REGION_NAME", "") or getattr(settings, "AWS_REGION", "")
    if not bucket or not region:
        raise RuntimeError("S3 bucket/region not configured")

    # 키 생성: uploads/{user_or_session}/.../uuid-원본파일명
    safe_name = _safe_filename(original_name)
    unique = uuid.uuid4().hex
    key = f"{prefix}{unique}-{safe_name}"

    s3 = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", getattr(settings, "AWS_ACCESS_KEY_ID", None)),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", getattr(settings, "AWS_SECRET_ACCESS_KEY", None)),
    )

    # 업로드
    extra_args = {"ContentType": getattr(django_file, "content_type", "application/octet-stream")}
    s3.upload_fileobj(django_file, bucket, key, ExtraArgs=extra_args)

    # 비서명 URL 반환 (virtual-hosted style)
    # 키에는 퍼센트 인코딩 필요(브라우저 안전), DB에는 이 "비서명 URL"만 저장
    encoded_key = quote(key)
    return f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}"
