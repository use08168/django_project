from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from uauth.models import UserDeletionStatus
from llm_integration.llmproxy.models import Conversation

User = get_user_model()

class Command(BaseCommand):
    help = "Delete accounts & conversations/messages whose deletion pending expired (>30d)."

    def handle(self, *args, **kwargs):
        now = timezone.now()
        qs = UserDeletionStatus.objects.filter(pending_until__lt=now)
        count = 0
        for uds in qs.select_related("user"):
            u = uds.user
            Conversation.objects.filter(user=u).delete()  # messages cascade
            u.delete()
            uds.delete()
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Purged {count} accounts"))
