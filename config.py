from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "27686895"))
API_HASH = environ.get("API_HASH", "0e996bd3891969ec5dfebf8bb3e39e94")
BOT_TOKEN = environ.get("BOT_TOKEN", "8456336413:AAFArfdOHON1b2FbABTbV-ncetvwFsUM_Jc")
STRING_SESSION = environ.get("STRING_SESSION", "") # User session for bot interaction
ADMINS = [int(admin) for admin in environ.get('ADMINS', '1246987713').split()]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003591540042"))
