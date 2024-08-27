Import  requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Download file from direct link
def download_file(url, file_name):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(file_name, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
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
        file_path = download_file(text, file_name)

        if file_path:
            await update.message.reply_text("Uploading the file to Telegram...")
            await update.message.reply_document(document=open(file_path, 'rb'))
        else:
            await update.message.reply_text("Failed to download the file.")
    else:
        await update.message.reply_text("Please send a valid direct download link.")

# Main function to start the bot
def main():
    application = Application.builder().token("5645711998:AAE8oAHzKi07iqcydKPnuFjzknlVa2MxxUQ").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
