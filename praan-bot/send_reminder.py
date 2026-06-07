import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot
from bot import send_transfusion_reminder

load_dotenv()

async def main():
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    await send_transfusion_reminder(bot=bot, transfusion_date="2026-06-14")
    print("✅ Reminder sent to Kanav.")

asyncio.run(main())
