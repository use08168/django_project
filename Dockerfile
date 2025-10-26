# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# 시스템 업데이트(필수 아님, 안정성 위해)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ❌ 문제의 COPY 라인 제거
# COPY llm_integration/requirements-extra.txt ./llm_extras.txt
# RUN pip install --no-cache-dir -r llm_extras.txt || true

COPY . .

# gunicorn 설정 파일 이름 일치 확인 (있으면 패스, 없으면 아래 줄 삭제)
# 예: 파일명을 gunicorn.conf.py 로 맞춘 상태
RUN python manage.py collectstatic --noinput

# entrypoint 사용할 거면 실행 권한 부여(선택)
# RUN chmod +x entrypoint.sh

CMD ["bash","-lc","python manage.py migrate && gunicorn project4.wsgi:application --config gunicorn.conf.py --bind 0.0.0.0:8000"]
