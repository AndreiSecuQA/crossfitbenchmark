import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
_raw_admin_id = os.environ.get("FIRST_ADMIN_ID", "")
try:
    FIRST_ADMIN_ID = int(_raw_admin_id)
except ValueError:
    FIRST_ADMIN_ID = None
REMINDER_HOURS = 3
