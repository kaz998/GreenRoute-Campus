from dotenv import load_dotenv
load_dotenv()
import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "greenroute-demo-secret-change-me")
    DATABASE = os.path.join(BASE_DIR, "data", "greenroute.db")
    JSON_SORT_KEYS = False
    WTF_CSRF_TIME_LIMIT = None
    APP_VERSION = "4.0"
