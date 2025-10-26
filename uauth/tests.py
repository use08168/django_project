from django.test import TestCase, Client

import uuid 
from django.urls import reverse
from uauth.models import Message, EmailVerification, User


# 테스트 시나리오 - 단위별 : 로그인, 회원가입, 채팅, 개인정보 수정, 히스토리 관리 
# 테스트 설계서 : 통합 테스트 - 테스트 시나리오 플로우로 연결 

class SignupFlowTest(TestCase):
    def setUp(self):
        self.signup_url = reverse('uauth:sign')
        self.ajax_send_code_url = reverse('uauth:ajax_send_code')
        self.valid_email = 'testuser@example.com'
        self.valid_password = "Test@1234"
        self.valid_username = "testuser"

    # 회원가입 단위 테스트
    def test_signup_flow(self):
        data = {
            'username': self.valid_username,
            'email': 'invalid-email',
            'password1': self.valid_password,
            'password2': self.valid_password,
            'agree': 'yes',
        }

        # 1. 유효하지 않은 이메일 형식
        response = self.client.post(self.signup_url, data)
        self.assertContains(response, "유효한 이메일 형식을 입력하세요.")
        self.assertFalse(User.objects.filter(username=data['username']).exists())

        # 2. 이메일 인증 코드 발송
        response = self.client.post(
            self.ajax_send_code_url,
            {'email': data['email']},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertJSONEqual(response.content, {"status": "ok", "message": "인증번호를 전송했습니다."})

        # 3. DB에 코드가 생성되었는지 확인
        code_obj = EmailVerification.objects.get(email=data['email'])
        self.assertFalse(code_obj.is_used)

        # 4. 회원가입 데이터 
        signup_data = {
            'username': self.valid_username,
            'email': self.valid_email,
            'password1': self.valid_password,
            'password2': self.valid_password,
            'agree': 'yes',
            'verification_code': code_obj.code
        }

        # 5. 회원가입 요청 
        response = self.client.post(self.signup_url, signup_data, follow=True)

        # 6. 성공적인 회원가입
        self.assertContains(response, "회원가입이 완료되었습니다. 로그인 해주세요.")

        # 7. 회원가입 후 로그인 페이지 이동
        self.assertTemplateUsed(response, 'uauth/login.html')

class LoginFlowTest(TestCase):
    def setUp(self):
        self.login_url = reverse('uauth:login')
        self.valid_email = 'testuser@example.com'
        self.valid_password = "Test@1234"
        self.valid_username = "testuser"

    # 로그인 단위 테스트
    def test_login_flow(self):
        # 사전 회원가입
        user = User.objects.create_user(
            username=self.valid_username,
            email=self.valid_email,
            password=self.valid_password
        )

        # 1. 로그인 시도
        response = self.client.post(self.login_url, {
            'username': self.valid_username,
            'password': self.valid_password
        }, follow=True)

        # 2. 로그인 성공 후 채팅 페이지 이동
        self.assertTemplateUsed(response, 'uauth/chat.html')

        # 3. 세션에 사용자 로그인 상태 확인
        user = response.context['user']
        self.assertTrue(user.is_authenticated)

    # 비밀번호 찾기 단위 테스트
    def test_password_reset_flow(self):
        pass 

"""
비밀번호 찾기
이메일 입력
인증 코드 발송 / 재발송
코드 확인

비밀번호 입력
비밀번호 재입력 
비밀번호 저장
> 완료 시 로그인 페이지 이동

"""