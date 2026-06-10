from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "27686895"))
API_HASH = environ.get("API_HASH", "0e996bd3891969ec5dfebf8bb3e39e94")
BOT_TOKEN = environ.get("BOT_TOKEN", "8583744005:AAHxiBsiOts0XT-yORJYuQptiYfOc2J5aAk")
STRING_SESSION = environ.get("STRING_SESSION", "BQGmd-8AgmBJV3pNboqqtAUFxmVRnOPQPstUJxBhl7qmvWYusWIm8xq6YKaeFQGLkxdzGc3Y1pb6izpVbzsr50453x5Mfalv4E8navwU86YwsXo55UFwKIBRRUKLKKbhW-t88v1m6DAvg89mCCM-Pnx3TTeosIF3cVi_uAfco4-_dsWSgf42oib5Lg4B3I9rBvkYuBIM8eo2pw9U_BOsU8XzSctTsyinCNcphjjGIR8NYeLjuyLk4j28QYrnkzfSWehVHCLgJaKkBg371mgh4tDlYTTWkdqyN4PJVbcZJABp542OJB9ES9Bkk4CRI56K04__hvPTb5E6rlDll9v991e8BsZ-AwAAAABKU4XBAA") # User session for bot interaction
ADMINS = [1246987713]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003591540042"))
