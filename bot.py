import aiohttp
import aiofiles
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import telegram  # Import the telegram module to handle errors like telegram.error.TimedOut

# Asynchronous download function
async def download_file(url, file_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(file_name, 'wb') as f:
                    await f.write(await response.read())
                return file_name
            return None

# Start command handler
async def start(update: Update, context):
    await update.message.reply_text("Hello! Send me a direct download link, and I'll upload the file to Telegram.")

# Handle messages with links
async def handle_message(update: Update, context):
    text = update.message.text

    # Validate if the text is a URL
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("Downloading the file...")
        file_name = "downloaded_file"
        
        # Download the file
        file_path = await download_file(text, file_name)

        if file_path:
            await update.message.reply_text("Uploading the file to Telegram...")
            try:
                await update.message.reply_document(document=open(file_path, 'rb'), timeout=120)
            except telegram.error.TimedOut:
                await update.message.reply_text("Failed to upload the file due to a timeout.")
        else:
            await update.message.reply_text("Failed to download the file.")
    else:
        await update.message.reply_text("Please send a valid direct download link.")

# Main function to start the bot
def main():
    application = Application.builder().token("YOUR_TELEGRAM_BOT_TOKEN").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
