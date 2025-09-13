import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from extractor import extract_text_from_pdf, parse_mcqs, write_csv

TOKEN = "7974993979:AAFFFeHfJJsAz93HhMHfyBF45fU9kJW9umw"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a PDF containing MCQs and I will convert it into CSV.")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = f"downloads/{update.message.document.file_name}"
    os.makedirs("downloads", exist_ok=True)
    await file.download_to_drive(file_path)

    text = extract_text_from_pdf(file_path)
    mcqs = parse_mcqs(text)

    output_path = file_path.replace(".pdf", ".csv")
    write_csv(mcqs, output_path)

    await update.message.reply_document(document=open(output_path, "rb"))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.FileExtension("pdf"), handle_pdf))
    app.run_polling()

if __name__ == "__main__":
    main()
