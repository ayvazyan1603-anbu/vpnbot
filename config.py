import os
from dotenv import load_dotenv

load_dotenv()

# Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "support")

# Prices
PRICE_1_MONTH = int(os.getenv("PRICE_1_MONTH", "299"))
PRICE_3_MONTHS = int(os.getenv("PRICE_3_MONTHS", "799"))
PRICE_6_MONTHS = int(os.getenv("PRICE_6_MONTHS", "1399"))
PRICE_12_MONTHS = int(os.getenv("PRICE_12_MONTHS", "2499"))

# Payment
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS", "Не настроено")

# 3x-ui
XUI_URL = os.getenv("XUI_URL")
XUI_USERNAME = os.getenv("XUI_USERNAME")
XUI_PASSWORD = os.getenv("XUI_PASSWORD")
XUI_API_TOKEN = os.getenv("XUI_API_TOKEN")
XUI_HOST = os.getenv("XUI_HOST")
XUI_PORT = int(os.getenv("XUI_PORT", "47506"))
