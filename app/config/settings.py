import os
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).parents[2] / ".env"
load_dotenv(dotenv_path)

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    LOGS_DIR_PATH= os.getenv("LOGS_DIR_PATH")