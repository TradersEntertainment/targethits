import os
from telegram import Bot
import logging

logger = logging.getLogger(__name__)

# Credentials from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = None
if TELEGRAM_TOKEN:
    bot = Bot(token=TELEGRAM_TOKEN)
else:
    logger.warning("TELEGRAM_TOKEN is not set. Notifications will be disabled.")

async def send_notification(message: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send telegram notification: {e}")

async def send_alert_error(error_msg: str):
    """E.g. Pyth Rate limit exceeded, ban warning"""
    try:
        await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ <b>SISTEM UYARISI</b> ⚠️\n\n{error_msg}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
