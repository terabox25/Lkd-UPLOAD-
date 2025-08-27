import logging
from telegram.ext import Application
from config import BOT_TOKEN
from plugins.aiquiz import aiquiz_handlers
from plugins.add_csv import addcsv_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    for h in aiquiz_handlers:
        app.add_handler(h)
    for h in addcsv_handlers:
        app.add_handler(h)

    logger.info("🤖 Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
