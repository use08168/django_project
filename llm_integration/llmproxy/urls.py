from django.urls import path
from . import views

app_name = "llm"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("chat/", views.chat_page, name="chat"),
    path("api/chat/history", views.chat_history, name="chat_history"),
    path("api/chat/send", views.chat_send, name="chat_send"),
    path("api/file/upload", views.file_upload, name="file_upload"),
    path("api/conversations", views.conversations_list, name="conversations_list"),
    path("api/conversations/new", views.conversations_new, name="conversations_new"),
    path("api/conversations/rename", views.conversations_rename, name="conversations_rename"),
    path("api/conversations/delete", views.conversations_delete, name="conversations_delete"),
    path("policy/terms", views.policy_terms, name="policy_terms"),
    path("policy/privacy", views.policy_privacy, name="policy_privacy"),
]
