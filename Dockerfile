FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# ✅ mysqlclient 빌드에 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스
COPY . .

# 정적 수집(장고 설정에 맞게)
RUN python manage.py collectstatic --noinput || true

# gunicorn 설정 파일 이름 확인
CMD ["bash","-lc","python manage.py migrate && gunicorn project4.wsgi:application --config gunicorn.conf.py --bind 0.0.0.0:8000"]
