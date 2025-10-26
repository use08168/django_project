from django.apps import AppConfig


class LlmproxyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "llm_integration.llmproxy"
    label = "llmproxy"
