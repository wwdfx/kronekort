# Kronekort Telegram Bot

A Telegram bot that monitors your Kronekort balance and notifies you when it changes.

## Features

- Register your Kronekort card number
- Automatic balance checking every 5 minutes
- Notifications when balance changes (with last transaction details)
- Manual balance check with `/balance` command

## Setup

### 1. Create Virtual Environment (Recommended)

**For Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**For Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Or use the setup script:**
- Linux/macOS: `bash setup.sh`
- Windows: `setup.bat`

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Get Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the bot token you receive

### 4. Configure Environment

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 5. Install Chrome/Chromium

The bot uses Selenium with Chrome to scrape the DNB website. Make sure you have Chrome or Chromium installed on your system.

### 6. Run the Bot

**Make sure your virtual environment is activated**, then:

```bash
python bot.py
```

## Usage

1. Start a conversation with your bot on Telegram
2. Send `/start` to begin
3. Enter your 12-digit Kronekort card number when prompted
4. The bot will automatically check your balance every 5 minutes
5. You'll receive notifications when your balance changes
6. Use `/balance` to manually check your balance anytime
7. Use `/updatecard` to update your card number

## Commands

- `/start` - Start the bot and register your card number
- `/balance` - Manually check your current balance
- `/updatecard` - Update your registered card number
- `/cancel` - Cancel current operation

## How It Works

1. The bot stores your card number in a local SQLite database
2. Every 5 minutes, it checks the balance on the DNB website
3. If the balance has changed, it parses the last transaction and sends you a notification
4. If the balance is unchanged, no notification is sent

## Notes

- The bot uses Selenium to interact with the DNB website, which requires Chrome/Chromium
- The first balance check after registration serves as the baseline
- Balance changes are detected by comparing the current balance with the last recorded balance
- The bot runs in headless mode (no browser window will open)

## Troubleshooting

- **"Could not get balance"**: The website structure may have changed, or there might be network issues
- **Bot not responding**: Check that your bot token is correct and the bot is running
- **Chrome driver errors**: Make sure Chrome/Chromium is installed and up to date

## Disclaimer

This bot is for personal use only. Make sure you comply with DNB's terms of service when using automated tools to access their website.

