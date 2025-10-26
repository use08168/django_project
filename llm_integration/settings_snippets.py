"""
Settings snippets to enable RDS MySQL and optional S3 storage.
Import these into your main settings (project4/settings.py) as needed.
"""
import os
from pathlib import Path


def configure_database(DATABASES: dict) -> dict:
    name = os.getenv("DB_NAME")
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    pwd = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "3306")
    if name and host and user and pwd:
        DATABASES["default"] = {
            "ENGINE": "django.db.backends.mysql",
            "NAME": name,
            "USER": user,
            "PASSWORD": pwd,
            "HOST": host,
            "PORT": port,
            "OPTIONS": {"charset": "utf8mb4"},
        }
    return DATABASES


def configure_s3(settings_module: object) -> None:
    bucket = os.getenv("AWS_S3_BUCKET")
    region = os.getenv("AWS_S3_REGION", "ap-northeast-2")
    if not bucket:
        return
    # Lazy minimal S3 config for static/media via django-storages
    settings_module.AWS_STORAGE_BUCKET_NAME = bucket
    settings_module.AWS_S3_REGION_NAME = region
    settings_module.AWS_DEFAULT_ACL = None
    settings_module.AWS_S3_ENDPOINT_URL = f"https://s3.{region}.amazonaws.com"
    settings_module.DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

