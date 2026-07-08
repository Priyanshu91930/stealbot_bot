from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "27686895"))
API_HASH = environ.get("API_HASH", "0e996bd3891969ec5dfebf8bb3e39e94")
BOT_TOKEN = environ.get("BOT_TOKEN", "8811056986:AAEhjHZjujjwhZNII97Y5-5yrvFS19pz6KQ")
STRING_SESSION = environ.get("STRING_SESSION", "BQGmd-8Ajv1Wbi98dq1zvhV3MPFbWNgHZafM2wFTGfU4EAEP0osrDBViCLoMGi0Cq0Q9yLG8dhXhM3v-HzoWxol7qBmrt7KRNt5Dbvs-mUhYBXxZpau6kSzip4CCpxmqLP6ONpd1_AChdONmQ0cdyICh1WIoz6TwWA15tsp0Q-9aWMaQ213wJ5Jf7oBQXTzHnkqi-8b_a0n6yCfuPXb3vJi23zoxB8d5psjFMwlnVBi4w_zd3ivk41NLzJT8i6gaEdnp2BNa_H3RXPsD808zwZgaoXPlGS2BPWxDznS-6XRSUaLVrSFDr7xGsYA-3gIvsMzDEuOgtbsQVa58HSRS4GrIpXIPHwAAAABKU4XBAA") # User session for bot interaction
ADMINS = [1246987713]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003591540042"))
