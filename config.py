from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "27686895"))
API_HASH = environ.get("API_HASH", "0e996bd3891969ec5dfebf8bb3e39e94")
BOT_TOKEN = environ.get("BOT_TOKEN", "8583744005:AAHxiBsiOts0XT-yORJYuQptiYfOc2J5aAk")
STRING_SESSION = environ.get("STRING_SESSION", "BQGmd-8ArvpbL63MUhYTuciu925waL1oMowjEK1n4i5HSXlM2ls6tG0cV0-KRRbZ65ArPWKEa1DEYvV12vC1zn2OKta3TMTxo5StYl5H223IcG51KkUK-RUR6UyjkOn5zS91XltAq_EVrbBjA_RvCANholkijlTUIXamikLo28B50cIYmMgs25EJ61StI7tV1Gqk0TyB35cAWTdI6BjK20Y-5Vy7AvciWq4EuUpDbZBi5V3AiQi2q8bVv8J_lqPLlXixWGKZLSqzPjdlyUFCNCgoRJZua-6Ns_n-5JDqdO9U4g99mInkGNCKDNsFn0cGcGcdu05P2ZiXcYhB2nfzVqzWbxvTjgAAAABKU4XBAA") # User session for bot interaction
ADMINS = [1246987713]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003591540042"))
