from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "37663759"))
API_HASH = environ.get("API_HASH", "8c279fdd3f2a8a1a441afca3766b855b")
BOT_TOKEN = environ.get("BOT_TOKEN", "8970579876:AAHDeoKyUTSHDV1zzgr_Ng9nw_HyBlAow9Y")
STRING_SESSION = environ.get("STRING_SESSION", "BQI-tA8AknXCqLVc7M4jaKOfUWA3Tr6GR1L3UJNI9VFxklI9RHAT_t9ihRztXAqTgzdGOrCYzs3MlLDXdKShM8YzqOtEm6UHOgj46NecLW4iASYAmJgtPN3mx9CidxwEEb0dmgsk1-jaldGK0kOPcO3DT-QQi0g4CMVA3BffP78ndolWyDfx4QxZ81p8ZTxZpjH50EvQDVNXVq0EMPvOtmBwLe2P08rH1rv2FE61Oknx1NIXhom4Oan8Z1_eJj0ydAr9PeKAiMk8jpZPvIvdYKPWiEEpZtmk4QnLyG0Gou_4eypOXU3MBlnUDUZlrf2eEfXN6F3xV0auQO9lQjA1Yytdto9eaQAAAAH6SxnVAA") # User session for bot interaction
ADMINS = [8494193109]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1004161131573"))
