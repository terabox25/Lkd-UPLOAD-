from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from plugins.utils import list_subjects, list_subsubjects, list_topics, list_tests, send_csv_as_quiz

async def aiquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subjects = list_subjects()
    if not subjects:
        await update.message.reply_text("❌ No quizzes available yet.")
        return
    kb = [[InlineKeyboardButton(s, callback_data=f"subject|{s}")] for s in subjects]
    await update.message.reply_text("📚 Choose a subject:", reply_markup=InlineKeyboardMarkup(kb))

async def aiquiz_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")

    if data[0] == "subject":
        subs = list_subsubjects(data[1])
        kb = [[InlineKeyboardButton(s, callback_data=f"sub|{data[1]}|{s}")] for s in subs]
        await query.edit_message_text(f"📘 Subject: {data[1]}\nChoose sub-subject:", reply_markup=InlineKeyboardMarkup(kb))

    elif data[0] == "sub":
        topics = list_topics(data[1], data[2])
        kb = [[InlineKeyboardButton(t, callback_data=f"topic|{data[1]}|{data[2]}|{t}")] for t in topics]
        await query.edit_message_text(f"📖 {data[2]} → Choose topic:", reply_markup=InlineKeyboardMarkup(kb))

    elif data[0] == "topic":
        tests = list_tests(data[1], data[2], data[3])
        kb = [[InlineKeyboardButton(t, callback_data=f"test|{data[1]}|{data[2]}|{data[3]}|{t}")] for t in tests]
        await query.edit_message_text(f"📝 {data[3]} → Choose test:", reply_markup=InlineKeyboardMarkup(kb))

    elif data[0] == "test":
        await query.edit_message_text(f"▶ Starting test {data[4]} ...")
        await send_csv_as_quiz(query.message.chat_id, data[1], data[2], data[3], data[4], context)

aiquiz_handlers = [
    CommandHandler("aiquiz", aiquiz_command),
    CallbackQueryHandler(aiquiz_navigation, pattern="^(subject|sub|topic|test)"),
      ]
