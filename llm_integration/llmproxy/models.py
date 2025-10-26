from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Conversation(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_key = models.CharField(max_length=64, db_index=True, blank=True, default="")
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # S3 보관 관련
    uploaded_pdf_url = models.URLField(blank=True, default="")   # 최근 발급한 presigned URL
    s3_key = models.CharField(max_length=512, blank=True, default="")  # 실제 S3 객체 키

    # 업로드된 PDF를 텍스트 컨텍스트로 보관
    pdf_context_md = models.TextField(blank=True, default="")
    pdf_context_attached = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.title or f"Conversation #{self.pk}"

class Message(models.Model):
    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    )
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    file_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:32]}"
