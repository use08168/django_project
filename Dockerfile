FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# (mysqlclient 쓰면 OS 패키지 필요 / PyMySQL 쓰면 이 블록 생략해도 됨)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential gcc default-libmysqlclient-dev pkg-config \
#   && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 전체 복사
COPY . .

# ⬇️ 파일이 있을 때만 설치
RUN if [ -f "llm_integration/requirements-extra.txt" ]; then \
      pip install --no-cache-dir -r llm_integration/requirements-extra.txt; \
    fi

RUN python manage.py collectstatic --noinput

# gunicorn 설정 파일 이름 확인(오타주의: gunicorn.conf.py)
CMD ["bash","-lc","python manage.py migrate && gunicorn project4.wsgi:application --config gunicorn.conf.py --bind 0.0.0.0:8000"]
