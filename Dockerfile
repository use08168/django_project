FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional extras for AWS/LLM if present
COPY llm_integration/requirements-extra.txt ./llm_extras.txt
RUN pip install --no-cache-dir -r llm_extras.txt || true

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["bash","-lc","python manage.py migrate && gunicorn project4.wsgi:application --config gunicorn.conf.py --bind 0.0.0.0:8000"]
