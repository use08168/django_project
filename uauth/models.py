from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Message(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_key = models.CharField(max_length=40, db_index=True, blank=True, default="")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]  # 오래된→최신

    def __str__(self):
        who = self.user.username if self.user_id else (self.session_key or "guest")
        return f"{who}: {self.content[:20]}"

class EmailVerification(models.Model):
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self, minutes=5):
        """5분 후 만료"""
        return timezone.now() > self.created_at + timedelta(minutes=minutes)

    def __str__(self):
        return f"{self.email} / {self.code} / used={self.is_used}"

class TempPassword(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    temp_pw = models.CharField(max_length=128)  # 암호화된 비밀번호 저장 가능
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self, minutes=30):
        return timezone.now() > self.created_at + timedelta(minutes=minutes)

    def __str__(self):
        return f"{self.user.email} / used={self.is_used}"


class UserDeletionStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="deletion_status")
    pending_since = models.DateTimeField(null=True, blank=True)
    pending_until = models.DateTimeField(null=True, blank=True)

    @property
    def is_pending(self) -> bool:
        return bool(self.pending_until and timezone.now() < self.pending_until)

    def start_pending(self, days: int = 30):
        now = timezone.now()
        self.pending_since = now
        self.pending_until = now + timedelta(days=days)
        self.save()

    def clear(self):
        self.pending_since = None
        self.pending_until = None
        self.save()
