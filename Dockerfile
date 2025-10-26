FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# ✅ mysqlclient 빌드에 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc pkg-config \
    default-libmysqlclient-dev \
    libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# (옵션) 추가 요구사항 있으면 시도하되 실패 무시
COPY llm_integration/requirements-extra.txt ./llm_extras.txt
RUN pip install --no-cache-dir -r llm_extras.txt || true

COPY . .

# ⚠️ collectstatic는 런타임에 돌리는 게 안전(환경변수/스토리지 의존)
#RUN python manage.py collectstatic --noinput

CMD ["bash","-lc","python manage.py migrate && python manage.py collectstatic --noinput && gunicorn project4.wsgi:application --config gunicorn.conf.py --bind 0.0.0.0:8000"]
