from django.urls import path
from uauth import views
from . import views

app_name = 'uauth'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('sign/', views.sign, name='sign'),
    path('chat/', views.chat, name='chat'),
    path('email/', views.email, name='email'),         # 이메일 입력
    path('password/', views.password, name='password'),    # 새 비밀번호 입력
    path("password_reset/", views.password_reset, name="password_reset"),
    path('terms/', views.terms, name='terms'),
    path("chat/api/send/", views.chat_send, name="chat_send"),
    path("chat/api/list/", views.chat_list, name="chat_list"),
    path("test-email/", views.test_email),
    path("email/send-code/", views.ajax_send_code, name="ajax_send_code"),
    path("email/verify-code/", views.ajax_verify_code, name="ajax_verify_code"),
    # JSON API for SPA
    path('api/login/', views.login_api, name='login_api'),
    path('api/sign/', views.sign_api, name='sign_api'),
    path('api/logout/', views.logout_api, name='logout_api'),
    path('api/password/request_temp/', views.password_request_temp_api, name='password_request_temp_api'),
    path('api/password/change/', views.password_change_api, name='password_change_api'),
    path('api/delete_request/', views.delete_request_api, name='delete_request_api'),
    path('api/restore/', views.restore_account_api, name='restore_account_api'),
]
