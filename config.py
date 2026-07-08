from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "27686895"))
API_HASH = environ.get("API_HASH", "0e996bd3891969ec5dfebf8bb3e39e94")
BOT_TOKEN = environ.get("BOT_TOKEN", "8811056986:AAEhjHZjujjwhZNII97Y5-5yrvFS19pz6KQ")
STRING_SESSION = environ.get("STRING_SESSION", "BQGmd-8AUZ8mGdKvE6JYKRDcoPz8Iy01QdZSIar_H2oTCuE0TAlyHZTPR9XCuoubpchO4lQST9pnci8CQRSz5-FujPOEi8Y6dBY9fj-oOsbvEJH-oB1Yu--vAVyfZCLOVyEcuz9gpChoEK8OmQr-MC0bZOKyJTuPEzhNoH-5G7n3KW9aYSetPgtMw2IVISZnDccRq7tRwnNeM2DKab9swf8dbw8VWHHkVaF5cr9l_K15oxhk31u-cFc30LIdecaDxHQOGBghAveGroeyuJU0biF0sIUS0TXIJ3JHoNzLK8bQUg86-90nI9VCVvARfNZH1rj_Ea-kIHhNdA90IL6GknXnQJUBqQAAAABKU4XBAA") # User session for bot interaction
ADMINS = [1246987713]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003591540042"))
