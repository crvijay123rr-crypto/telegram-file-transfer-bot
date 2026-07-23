import os

# Telegram API Credentials (my.telegram.org se lein)
API_ID = int(os.getenv("API_ID", "1234567"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# MongoDB Connection URL
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=w&writeConcern=majority")
DB_NAME = "telegram_transfer_bot"

# Admin User IDs (Yahan apni Telegram ID daalein jahan buy request aur stats jayenge)
ADMIN_IDS = [123456789] 
