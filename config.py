from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "27686895"))
API_HASH = environ.get("API_HASH", "0e996bd3891969ec5dfebf8bb3e39e94")
BOT_TOKEN = environ.get("BOT_TOKEN", "8811056986:AAEhjHZjujjwhZNII97Y5-5yrvFS19pz6KQ")
STRING_SESSION = environ.get("STRING_SESSION", "BQGmd-8ASsYhTQ9_9JwftQk0jn_xb63j-_uoY97MFXuQwTUD-KjR9LYtek3Jp4m7CFnvEF2TqEPVxqv1K78OVFa2wCuG4uiPDwMSmyjRxm38dpTg9M7rSAtTzueWwg1uiQIboFwknGrH2-5rO6au85JYHJVZNKSwDeOCKx2lDRsMQptXqJucEjs6-MkX_DuYP9FsVvCJcQe1t5aoJXHFPK2qwXHITH5k5ePejysKTvL21NXc1S6hyVVJzMuTluehUmXct09yF1_1eYO0gfnhYOxkQwxQYTaF6gQpqjSEEe0XUiasIk5cdFOjUrHmtKaEMxksRNSTexbbXhVVF4uzJVohGcTLegAAAABKU4XBAA") # User session for bot interaction
ADMINS = [1246987713]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003591540042"))
