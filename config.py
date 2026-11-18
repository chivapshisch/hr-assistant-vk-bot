import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as env_file:
        for line in env_file:
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                clean_value = value.strip().strip("'").strip('"')
                if clean_value.lower() not in ("none", "null", ""):
                    os.environ[key.strip()] = clean_value

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
VK_CONFIRMATION_STRING = os.getenv("VK_CONFIRMATION_STRING")
VK_TOKEN = os.getenv("VK_TOKEN")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
REDIS_STORAGE_URL = os.getenv("REDIS_STORAGE_URL", "redis://127.0.0.1:6379/1")

DB_PATH = os.path.join(BASE_DIR, "data", "baza_hr_chik.db")
