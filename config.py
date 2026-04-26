import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Adminlarni vergul bilan ajratilgan stringdan listga o'tkazamiz
ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS", "").split(",") if admin_id]
