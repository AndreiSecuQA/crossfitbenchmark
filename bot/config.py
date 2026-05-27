import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
FIRST_ADMIN_ID = int(os.environ["FIRST_ADMIN_ID"])
REMINDER_HOURS = 3
