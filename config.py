from os import environ
from dotenv import load_dotenv

load_dotenv()

API_ID = int(environ.get("API_ID", "37663759"))
API_HASH = environ.get("API_HASH", "8c279fdd3f2a8a1a441afca3766b855b")
BOT_TOKEN = environ.get("BOT_TOKEN", "8970579876:AAHDeoKyUTSHDV1zzgr_Ng9nw_HyBlAow9Y")
STRING_SESSION = environ.get("STRING_SESSION", "BQGmd-8Af2OyBWHzXHila4kqRwJO8v2_2WzrS9-oCBa9FXBm1ZWlAy_0iaInpbZdftpIvzHqNyjrz3OvSC71TzWeYwPQDyWoM9KCE_PHEpff1AibN7B1Y4fAKUBLlYSDz8rCzDp3eiQM1qGmRpoQi2dt2loPpL5JKdIbEhUuCH6YSBI_NmkjUQxuokGcgV5djpljr89y02yFGdvYBMETkGUEluIapbVOdXjOyKCW7VE8FQ40NYrGdbwnwXUhWctDWgSL_1oje4NWAcwBpiQqV4LR23mlUjxWzNxRlK7l9RPKpVOxRyep0Er9quYhAQBPL2RPuC38eYz3XRscpgXfzuF2jXK4RQAAAAH6SxnVAA") # User session for bot interaction
ADMINS = [8494193109]
DB_URI = environ.get("DB_URI", "mongodb+srv://anihubyt:Zxcvbnmm9193@cluster0.qv5tu12.mongodb.net/?appName=Cluster0")
DB_NAME = environ.get("DB_NAME", "banana_bot")
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1004161131573"))
