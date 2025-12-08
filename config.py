import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')

# DNB Website URL
DNB_BALANCE_URL = 'https://www.dnb.no/kort/kronekort/saldo/'

# Database file
DATABASE_FILE = 'kronekort.db'

# Check interval in seconds (5 minutes = 300 seconds)
CHECK_INTERVAL = 300

