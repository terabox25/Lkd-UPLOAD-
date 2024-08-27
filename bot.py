import os
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import telegram
from telegram.request import HTTPXRequest  # Import the HTTPXRequest for setting custom timeout

# Function to download video using yt-dlp
def download_video(url, file_name):
    ydl_opts = {
        'outtmpl': file_name,
        'format': 'best',  # You can change the format here (e.g., 'bestaudio' for audio only)
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return file_name

# Start command handler
async def start(update: Update, context):
    await update.message.reply_text("Hello! Send me a direct download link, and I'll upload the file to Telegram.")

# Handle messages with links
async def handle_message(update: Update, context):
    text = update.message.text

    # Validate if the text is a URL
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("Downloading the file...")

        file_name = "downloaded_video"  # Default filename
        try:
            # Download the video using yt-dlp
            file_path = download_video(text, file_name)

            # Check file size
            file_size = os.path.getsize(file_path)
            max_file_size = 2 * 1024 * 1024 * 1024  # 2 GB

            if file_size > max_file_size:
                await update.message.reply_text("The file is too large to upload to Telegram (max size is 2 GB).")
            else:
                await update.message.reply_text("Uploading the file to Telegram...")
                try:
                    await update.message.reply_document(document=open(file_path, 'rb'))
                except telegram.error.TimedOut:
                    await update.message.reply_text("Failed to upload the file due to a timeout.")
        except Exception as e:
            await update.message.reply_text(f"Failed to download the file: {e}")
    else:
        await update.message.reply_text("Please send a valid direct download link.")

# Main function to start the bot
def main():
    # Set a custom timeout for requests
    request = HTTPXRequest(connect_timeout=120, read_timeout=120)

    # Build the application with custom request settings
    application = Application.builder().token("5645711998:AAE8oAHzKi07iqcydKPnuFjzknlVa2MxxUQ").request(request).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
