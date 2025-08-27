from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, filters, ContextTypes
from config import ADMIN_IDS, QUIZ_ROOT
import os

WAIT_SUBJECT, WAIT_SUBSUB, WAIT_TOPIC, WAIT_FILE = range(4)
temp_data = {}

async def addcsv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    await update.message.reply_text("📚 Enter Subject name:")
    return WAIT_SUBJECT

async def subject_received(update, context):
    temp_data["subject"] = update.message.text
    await update.message.reply_text("📘 Enter Sub-Subject name:")
    return WAIT_SUBSUB

async def subsub_received(update, context):
    temp_data["subsub"] = update.message.text
    await update.message.reply_text("📖 Enter Topic name:")
    return WAIT_TOPIC

async def topic_received(update, context):
    temp_data["topic"] = update.message.text
    await update.message.reply_text("📂 Send CSV file now:")
    return WAIT_FILE

async def file_received(update, context):
    doc = update.message.document
    file = await doc.get_file()
    os.makedirs(f"{QUIZ_ROOT}/{temp_data['subject']}/{temp_data['subsub']}/{temp_data['topic']}", exist_ok=True)
    path = f"{QUIZ_ROOT}/{temp_data['subject']}/{temp_data['subsub']}/{temp_data['topic']}/test1.csv"
    await file.download_to_drive(path)
    await update.message.reply_text(f"✅ Saved as {path}")
    return ConversationHandler.END

addcsv_handlers = [
    ConversationHandler(
        entry_points=[CommandHandler("addaicsv", addcsv_command)],
        states={
            WAIT_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, subject_received)],
            WAIT_SUBSUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, subsub_received)],
            WAIT_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, topic_received)],
            WAIT_FILE: [MessageHandler(filters.Document.ALL, file_received)],
        },
        fallbacks=[]
    )
  ]
