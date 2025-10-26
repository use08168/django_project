from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.conf import settings
from datetime import datetime
from .models import Message, EmailVerification, TempPassword, UserDeletionStatus  # ★ EmailVerification 함께 import
import re
from django.utils.crypto import get_random_string

# 이메일 발송에 필요한 것들
from django.core.mail import send_mail
from django.utils import timezone
import random, string

# 유효성 검사
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

# ---------------------------
# 공용 유틸 (views.py 안에 포함)
# ---------------------------
def generate_code(length: int = 6) -> str:
    """6자리 숫자 코드 생성 (000000 가능)"""
    return ''.join(str(random.randint(0, 9)) for _ in range(length))


def send_verification_email(email: str, code: str) -> None:
    """인증번호 이메일 발송"""
    subject = "[CHATIVE] 이메일 인증번호 안내"
    message = (
        f"안녕하세요.\n\n"
        f"요청하신 인증번호는 {code} 입니다.\n"
        f"유효시간: 5분\n\n"
        f"본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)

def index(request):
    # SPA 구조로 통합: 루트는 LLM 메인으로 이동
    return redirect('/llm/')


def login(request):
    # 템플릿 사용 대신 SPA 메인으로 유도
    return redirect('/llm/')

@require_POST
def login_api(request):
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""
    if not email or not password:
        return JsonResponse({"ok": False, "message": "이메일과 비밀번호를 입력하세요."})
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "message": "이메일 주소 형식이 올바르지 않습니다."})
    try:
        username_for_auth = User.objects.get(email=email).username
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "message": "이메일 또는 비밀번호를 잘못 입력했습니다. 다시 입력하세요."})
    user = authenticate(request, username=username_for_auth, password=password)
    if user and user.is_active:
        # 삭제 대기 여부 확인
        uds, _ = UserDeletionStatus.objects.get_or_create(user=user)
        if uds.is_pending:
            return JsonResponse({"ok": False, "pending": True, "message": "삭제 예정 계정입니다. 복구 하시겠습니까?"})
        auth_login(request, user)
        request.session.cycle_key()
        # 임시비밀번호 여부 확인
        temp_exists = TempPassword.objects.filter(user=user, is_used=False).order_by('-created_at').first()
        return JsonResponse({"ok": True, "require_password_change": bool(temp_exists)})
    return JsonResponse({"ok": False, "message": "아이디/이메일 또는 비밀번호가 올바르지 않습니다."})

def chat(request):
    return redirect('/llm/chat/')


def sign(request):
    return redirect('/llm/')

@require_POST
def sign_api(request):
    email     = (request.POST.get("email", "") or "").strip().lower()
    password1 = request.POST.get("password1", "")
    password2 = request.POST.get("password2", "")
    agree     = request.POST.get("agree")
    if not email or not password1 or not password2:
        return JsonResponse({"ok": False, "message": "모든 항목을 입력하세요."})
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "message": "유효한 이메일 형식을 입력하세요."})
    if password1 != password2:
        return JsonResponse({"ok": False, "message": "비밀번호가 일치하지 않습니다."})
    if not agree:
        return JsonResponse({"ok": False, "message": "이용약관에 동의해야 합니다."})
    if User.objects.filter(email=email).exists():
        return JsonResponse({"ok": False, "message": "이미 사용 중인 이메일입니다."})
    # 아이디 대신 이메일을 username으로 사용
    User.objects.create_user(username=email, email=email, password=password1)
    return JsonResponse({"ok": True})

def logout_api(request):
    auth_logout(request)
    return JsonResponse({"ok": True})


def _validate_password(pw: str) -> bool:
    import re
    if not (5 <= len(pw) <= 16):
        return False
    # 2종류 이상 혼용 (대소문자/숫자/특수문자 중)
    classes = 0
    classes += 1 if re.search(r"[A-Z]", pw) else 0
    classes += 1 if re.search(r"[a-z]", pw) else 0
    classes += 1 if re.search(r"\d", pw) else 0
    classes += 1 if re.search(r"[^\w]", pw) else 0
    return classes >= 2


@require_POST
def password_request_temp_api(request):
    email = (request.POST.get('email') or '').strip().lower()
    if not email:
        return JsonResponse({"ok": False, "message": "이메일을 입력하세요."})
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "message": "없는 이메일입니다."})
    temp_pw = get_random_string(length=8)
    user.set_password(temp_pw)
    user.save()
    TempPassword.objects.create(user=user, temp_pw=temp_pw, is_used=False)
    try:
        send_temp_password_email(user, temp_pw)
    except Exception as e:
        return JsonResponse({"ok": False, "message": f"메일 발송 실패: {e}"})
    return JsonResponse({"ok": True})


@require_POST
def password_change_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "로그인이 필요합니다."}, status=401)
    current = request.POST.get('current_password') or ''
    p1 = request.POST.get('password1') or ''
    p2 = request.POST.get('password2') or ''
    if not request.user.check_password(current):
        return JsonResponse({"ok": False, "message": "현재 비밀번호가 올바르지 않습니다."})
    if p1 != p2:
        return JsonResponse({"ok": False, "message": "비밀번호가 일치하지 않습니다."})
    if not _validate_password(p1):
        return JsonResponse({"ok": False, "message": "비밀번호 규칙을 확인하세요."})
    request.user.set_password(p1)
    request.user.save()
    # mark temp passwords used
    TempPassword.objects.filter(user=request.user, is_used=False).update(is_used=True)
    return JsonResponse({"ok": True})


@require_POST
def delete_request_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "로그인이 필요합니다."}, status=401)
    uds, _ = UserDeletionStatus.objects.get_or_create(user=request.user)
    uds.start_pending(days=30)
    auth_logout(request)
    return JsonResponse({"ok": True})


@require_POST
def restore_account_api(request):
    email = (request.POST.get('email') or '').strip().lower()
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "message": "없는 이메일입니다."})
    uds, _ = UserDeletionStatus.objects.get_or_create(user=user)
    if uds.is_pending:
        uds.clear()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "message": "복구 대상이 아닙니다."})


def terms(request):
    return redirect('/llm/')


# --- 비밀번호 재설정(임시) ---
def email(request):
    return redirect('/llm/')

def ajax_verify_code(request):
    email = (request.POST.get("email") or "").strip().lower()
    code  = (request.POST.get("code")  or "").strip()

    if not email or not code:
        return JsonResponse({"status": "error", "message": "이메일과 코드를 모두 입력하세요."})

    rec = EmailVerification.objects.filter(email=email, is_used=False).order_by("-created_at").first()
    if not rec:
        return JsonResponse({"status": "error", "message": "인증 요청 기록이 없습니다."})
    if rec.is_expired(5):
        return JsonResponse({"status": "error", "message": "인증번호가 만료되었습니다. 다시 요청하세요."})
    if rec.code != code:
        return JsonResponse({"status": "error", "message": "인증번호가 올바르지 않습니다."})

    # 코드 사용 처리 + 세션 플래그 세팅
    rec.is_used = True
    rec.save()
    request.session["email_verified"] = True
    request.session["verified_email"] = email

    return JsonResponse({"status": "ok", "message": "인증이 완료되었습니다."})

from django.contrib.auth import authenticate, login as auth_login

def password(request):
    if request.method == "POST":
        pw1 = request.POST.get("password1","")
        pw2 = request.POST.get("password2","")
        if not pw1 or not pw2:
            messages.error(request,"새 비밀번호를 모두 입력하세요.")
        elif pw1 != pw2:
            messages.error(request,"두 비밀번호가 일치하지 않습니다.")
        elif not request.session.get("email_verified"):
            messages.error(request,"이메일 인증이 필요합니다.")
            return redirect("uauth:email")
        else:
            email = request.session.get("verified_email")
            try:
                user = User.objects.get(email=email)
                user.set_password(pw1)    # ← 해시로 저장
                user.is_active = True
                user.save()
            except User.DoesNotExist:
                # 아직 유저가 없다면 새로 생성 (아이디=이메일 전략)
                user = User.objects.create_user(username=email, email=email, password=pw1)
                user.is_active = True
                user.save()

            # 세션 정리
            request.session.pop("email_verified", None)
            request.session.pop("verified_email", None)

            messages.success(request, "비밀번호가 설정되었습니다. 로그인해 주세요.")
            return redirect("uauth:login")

    return redirect('/llm/')


# 임시 비밀번호 생성 + 이메일 발송
def generate_temp_password(length=8):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

def send_temp_password_email(user, temp_pw):
    send_mail(
        subject="임시 비밀번호 발송",
        message=f"임시 비밀번호: {temp_pw}",
        from_email="no-reply@yoursite.com",
        recipient_list=[user.email],
        fail_silently=False,
    )

def password_reset(request):
    step = int(request.POST.get('step', 1))
    email_address = request.POST.get('email', '').strip()
    context = {'step': step, 'email': email_address}

    # STEP 1: 이메일 입력 → 임시 비밀번호 발송
    if step == 1 and request.method == 'POST':
        email_address = request.POST.get('email','').strip()

        try:
            user = User.objects.get(email=email_address)
        except User.DoesNotExist:
            messages.error(request, "등록되지 않은 이메일입니다.")
            return render(request, 'uauth/password_reset.html', context)

        temp_pw = get_random_string(length=8)  # 임시 비밀번호 생성
        user.set_password(temp_pw)
        user.save()
        send_temp_password_email(user, temp_pw)  # user 객체와 함께 전달
        messages.success(request, "임시 비밀번호가 이메일로 발송되었습니다.")
        context['step'] = 2
        return render(request, 'uauth/password_reset.html', context)

    # STEP 2: 임시 비밀번호 입력 → 인증
    if step == 2 and request.method == 'POST':
        temp_pw = request.POST.get('temp_password', '').strip()
    try:
        user = User.objects.get(email=email_address)
    except User.DoesNotExist:
        # messages.error(request, "등록되지 않은 이메일입니다.")
        context['step'] = 1
        return render(request, 'uauth/password_reset.html', context)

        # 임시 비밀번호 인증 성공 → 자동 로그인 후 STEP 3
        user = authenticate(username=user.username, password=temp_pw)
    if user:
        auth_login(request, user)
        context['step'] = 3
        return render(request, 'uauth/password_reset.html', context)
    else:
        messages.error(request, "임시 비밀번호가 올바르지 않습니다.")
        return render(request, 'uauth/password_reset.html', context)
    
    # STEP 3: 새 비밀번호 입력 → 변경 완료
    # if step == 3 and request.method == 'POST':
    #     password1 = request.POST.get('password1', '')
    #     password2 = request.POST.get('password2', '')

    #     if password1 != password2:
    #         messages.error(request, "비밀번호가 일치하지 않습니다.")
    #         context['step'] = 3
    #         return render(request, 'uauth/password_reset.html', context)

    #     if len(password1) < 5 or len(password1) > 16:
    #         messages.error(request, "비밀번호는 5~16자여야 합니다.")
    #         context['step'] = 3
    #         return render(request, 'uauth/password_reset.html', context)

    #     # 현재 로그인한 사용자 비밀번호 변경
    #     user = request.user
    #     user.set_password(password1)
    #     user.save()
    #     messages.success(request, "비밀번호가 변경되었습니다. 로그인하세요.")
    #     return redirect('uauth:login')

    # 초기 화면 (STEP 1)
    # context['step'] = 1
    # return render(request, 'uauth/password_reset.html', context)
    

# ---------------------------
# 채팅 API
# ---------------------------
def _ensure_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


@require_POST
def chat_send(request):
    """메시지 저장 API (로그인 없어도 동작)"""
    session_key = _ensure_session_key(request)
    content = (request.POST.get("content") or "").strip()
    if not content:
        return JsonResponse({"ok": False, "error": "내용이 비었습니다."}, status=400)

    msg = Message.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=session_key,
        content=content,
    )
    return JsonResponse({
        "ok": True,
        "item": {
            "id": msg.id,
            "content": msg.content,
            "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "me": True,
        }
    })


def chat_list(request):
    """최근 50개 메시지 조회"""
    qs = Message.objects.order_by("-id")[:50]
    items = [
        {
            "id": m.id,
            "content": m.content,
            "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "me": (request.user.is_authenticated and m.user_id == request.user.id)
                  or (m.session_key and m.session_key == request.session.session_key),
        }
        for m in reversed(qs)  # 오래된→최신
    ]
    return JsonResponse({"ok": True, "items": items})


# ---------------------------
# 메일 테스트 & 인증코드 발송
# ---------------------------
def test_email(request):
    to = "use08168@gmail.com"  # ← 본인 실제 이메일로 변경!
    sent = send_mail(
        subject="[테스트] Django 이메일 발송 확인",
        message="이메일 설정이 정상 작동합니다.",
        from_email=settings.DEFAULT_FROM_EMAIL,  # settings에 설정된 발신자
        recipient_list=[to],
        fail_silently=False,  # 실패 시 예외 발생 → 콘솔에서 원인 확인 가능
    )
    return HttpResponse(f"✅ send_mail 반환값: {sent} (1이면 성공) / 받는이={to}")


@require_POST
def ajax_send_code(request):
    """
    이메일 인증 코드 발송 (AJAX)
    - POST: email
    """
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"status": "error", "message": "이메일을 입력해주세요."})

    # 최근 60초 이내 재요청 제한
    recent = EmailVerification.objects.filter(email=email).order_by("-created_at").first()
    if recent and (timezone.now() - recent.created_at).total_seconds() < 60:
        return JsonResponse({"status": "error", "message": "너무 자주 요청했습니다. 잠시 후 다시 시도하세요."})

    # 코드 생성 & 저장
    code = generate_code(6)
    EmailVerification.objects.create(email=email, code=code)

    # 메일 발송
    try:
        send_verification_email(email, code)
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"메일 발송 실패: {e}"})

    return JsonResponse({"status": "ok", "message": "인증번호를 전송했습니다."})


def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "이메일을 입력해주세요.")
            return render(request, "uauth/password_reset.html")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "등록되지 않은 이메일입니다.")
            return render(request, "uauth/password_reset.html")

        # 임시 비밀번호 생성
        temp_password = get_random_string(length=10)  # 랜덤 10자리
        user.set_password(temp_password)
        user.save()

        # 이메일 발송
        try:
            send_mail(
                subject="[YourService] 임시 비밀번호 안내",
                message=f"임시 비밀번호: {temp_password}\n로그인 후 꼭 비밀번호를 변경해주세요.",
                from_email="noreply@yourservice.com",
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, "임시 비밀번호가 이메일로 전송되었습니다.")
            return redirect("uauth:login")
        except Exception as e:
            messages.error(request, f"메일 발송 실패: {e}")
            return render(request, "uauth/password_reset.html")

    return render(request, "uauth/password_reset.html")

def password_reset(request):
    # 템플릿 기반 다단계 비번 재설정은 사용하지 않음 (SPA API 사용)
    return redirect('/llm/')

def password_reset_request(request):
    # 템플릿 기반 요청도 비활성화
    return redirect('/llm/')
