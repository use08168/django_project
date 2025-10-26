# 04_project/llm_integration/llmproxy/utils/llm_client.py
import os
import requests
from django.conf import settings

class LLMClient:
    """
    RunPod FastAPI (/v1/chat) 래퍼.
    Django 쪽은 attachments를 선택적으로 보낼 수 있게 하되,
    RunPod API가 첨부를 직접 받지 않으므로 메시지에 녹여 보낸다.
    """
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base = (base_url or getattr(settings, "RUNPOD_API_BASE", "")).rstrip("/")
        if not self.base:
            raise RuntimeError("RUNPOD_API_BASE is not set")
        self.timeout = timeout or int(getattr(settings, "RUNPOD_TIMEOUT", 120))

    def chat(self, messages, *, user_id="anon@local", session_id="default",
             max_tokens=1024, temperature=0.7, top_p=0.9, repetition_penalty=1.05,
             k_internal=6, k_external=0, cap_internal=1200, cap_external=1500,
             attachments=None) -> dict:
        # attachments에 markdown이 있으면 "system" 메시지로 합성
        merged = []
        # 시스템/유저/어시스턴트 순서를 유지
        for m in messages:
            if not m: 
                continue
            role = m.get("role")
            content = (m.get("content") or "").strip()
            if role in ("system", "user", "assistant") and content:
                merged.append({"role": role, "content": content})

        if attachments:
            md_blobs = []
            for att in attachments:
                if att.get("type") == "markdown" and att.get("content"):
                    name = att.get("name") or "context.md"
                    md_blobs.append(f"[{name}]\n{att['content']}")
            if md_blobs:
                merged.append({
                    "role": "system",
                    "content": "다음은 사용자 업로드 문서에서 추출한 컨텍스트입니다. 문서를 그대로 복붙하지 말고 요약/참조만 하세요.\n\n" + "\n\n---\n\n".join(md_blobs)
                })

        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "messages": merged,
            "k_internal": k_internal,
            "k_external": k_external,
            "cap_internal": cap_internal,
            "cap_external": cap_external,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
        }
        url = f"{self.base}/v1/chat"
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
