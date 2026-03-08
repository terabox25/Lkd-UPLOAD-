import csv

import logging

import asyncio
import re
from io import StringIO

from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import (

    Application, CommandHandler, MessageHandler, filters,

    CallbackQueryHandler, ContextTypes, ConversationHandler

)

from telegram.error import RetryAfter

from helpers.db import users_collection

from config import ADMIN_ID
import g4f
# Conversation states

UPLOAD_CSV, COLLECT_TEXT, CHOOSE_DESTINATION, CHOOSE_CHANNEL = range(4)

user_state = {}

user_csv_text = {}  # store text CSV per user

MODELS = [
    "gpt-4o",
    "gpt-4",
    "gpt-3.5-turbo",
    "mixtral-8x7b",
]
# ===============================
# VALIDATE REAL CSV
# ===============================

def is_real_csv(text: str):

    lines = text.strip().split("\n")

    if len(lines) < 2:
        return False

    comma_count = lines[0].count(",")

    if comma_count < 6:
        return False

    return True


# ===============================
# VALIDATE MCQ
# ===============================

def validate_mcq(row):

    q = row.get("Question")
    a = row.get("Option A")
    b = row.get("Option B")
    c = row.get("Option C")
    d = row.get("Option D")
    ans = row.get("Answer")

    if not all([q, a, b, c, d, ans]):
        return False

    if ans not in ["A", "B", "C", "D"]:
        return False

    return True


# ===============================
# AI GENERATOR
# ===============================

def generate_ai_response(prompt):

    for model in MODELS:

        try:

            response = g4f.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )

            if not response:
                continue

            result = response.strip()
            result = result.replace("```csv", "").replace("```", "").strip()

            if len(result) < 50:
                continue

            if is_real_csv(result):
                logging.info(f"AI success with {model}")
                return result

        except Exception as e:
            logging.warning(f"{model} failed: {e}")

    return None


# ===============================
# /uploadcsv
# ===============================

# -------------------------------

# /uploadcsv Command

# -------------------------------

async def upload_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    user_info = users_collection.find_one({'user_id': user_id})

    now = datetime.now()

    # Access check

    if user_id == ADMIN_ID:

        pass_access = True

    elif user_info and user_info.get('authorized', False):

        expires_on = user_info.get('expires_on')

        pass_access = expires_on and expires_on > now

    else:

        pass_access = False

    if not pass_access:

        await update.message.reply_text(

            "⚠️ Your free trial has expired.\nContact admin for full access. @lkd_ak"

        )

        return ConversationHandler.END

    # Ask user how to upload

    keyboard = [

        [InlineKeyboardButton("📎 Upload CSV File", callback_data='file')],

        [InlineKeyboardButton("✍️ Paste CSV Text", callback_data='text')]

    ]

    await update.message.reply_text(
        "📂 *Upload your CSV file or paste MCQs in text format*\n\n"
        "🧠 Bot aapke pasted MCQs ko automatically CSV format me samajh lega.\n\n"
        "*📌 Required CSV Format (copy & paste):*\n\n"
        "```csv\n"
        "Mene jo question or unke answe bheje hai unko csv ꜰᴏʀᴍᴀᴛ:\n"
        "Question,Option A,Option B,Option C,Option D,Answer,Description\n"
        "*📝 Important Rules:*\n"
        "• ✅ Answer sirf **A / B / C / D** format me ho\n"
        "• ✅ Description **240 characters se zyada nahi honi chahiye**\n"
        "• ❌ Extra columns ya blank rows na ho\n\n"
        "```\n\n"
        "👉 *How would you like to upload your MCQs?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return UPLOAD_CSV

# -------------------------------

# Handle choice: file or text

# -------------------------------

async def handle_upload_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if query.data == "file":

        await query.edit_message_text("📁 Please send your CSV file now.")

        return UPLOAD_CSV

    elif query.data == "text":

        user_csv_text[user_id] = []

        await query.edit_message_text(

            "📝 Send your CSV data in text format.\n"

            "You can send multiple messages. When finished, type /done."

        )

        return COLLECT_TEXT

# -------------------------------

# Collect CSV text messages

# -------------------------------

async def collect_text_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    text = update.message.text.strip()

    if user_id not in user_csv_text:

        user_csv_text[user_id] = []

    user_csv_text[user_id].append(text)

    await update.message.reply_text("✅ Added! Send more or type /done when finished.")

# -------------------------------

# When user types /done

# -------------------------------
# ===============================
# DONE
# ===============================

async def done_collecting(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    csv_text = "\n".join(user_csv_text.get(user_id, []))

    if not csv_text:

        await update.message.reply_text("No data received")

        return ConversationHandler.END


    # ===============================
    # DETECT CSV OR TEXT
    # ===============================

    if not is_real_csv(csv_text):

        await update.message.reply_text("🤖 AI converting text to MCQ...")

        prompt = f"""
Convert the TEXT into MCQ CSV

Format:
Question,Option A,Option B,Option C,Option D,Answer,Description

Rules:
Answer must be A/B/C/D
Description < 240 char
Return ONLY CSV

TEXT:
{csv_text}
"""

        csv_text = generate_ai_response(prompt)

        if not csv_text:

            await update.message.reply_text("AI conversion failed")

            return ConversationHandler.END


    csv_file = StringIO(csv_text)

    reader = csv.DictReader(csv_file)

    questions = []

    for row in reader:

        row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}

        if validate_mcq(row):

            questions.append(row)

        else:

            logging.warning("Invalid MCQ skipped")


    if not questions:

        await update.message.reply_text("No valid MCQs found")

        return ConversationHandler.END


    context.user_data['questions'] = questions


    keyboard = [
        [InlineKeyboardButton("Bot", callback_data='bot')],
        [InlineKeyboardButton("Channel", callback_data='channel')]

    ]

    await update.message.reply_text(

        f"{len(questions)} MCQs ready",

        reply_markup=InlineKeyboardMarkup(keyboard)

    )

    return CHOOSE_DESTINATION

    

# -------------------------------

# Handle CSV File Upload (merged with advanced checks)

# -------------------------------

async def handle_csv_file(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    try:

        file = await update.message.document.get_file()

        file_path = f"{file.file_id}.csv"

        await file.download_to_drive(file_path)

        # Read file and remove empty lines

        with open(file_path, 'r', encoding='utf-8-sig') as f:

            lines = [line.strip() for line in f if line.strip()]

        expected_headers = ["Question", "Option A", "Option B", "Option C", "Option D", "Answer", "Description"]

        # Check header

        first_line = lines[0] if lines else ""

        has_header = any(key.lower() in first_line.lower() for key in ["question", "option", "answer", "description"])

        if not has_header:

            lines.insert(0, ",".join(expected_headers))

            with open(file_path, 'w', encoding='utf-8', newline='') as f:

                f.write("\n".join(lines))

            await update.message.reply_text("ℹ️ Header missing detected. Default header added automatically ✅")

        # Read CSV properly

        with open(file_path, 'r', encoding='utf-8-sig') as f:

            reader = csv.DictReader(f)

            reader.fieldnames = [h.strip().title() for h in reader.fieldnames]

            questions = []

            for row in reader:

                clean_row = {k.strip().title(): (v.strip() if v else "") for k, v in row.items()}

                if not any(clean_row.values()):

                    continue

                questions.append(clean_row)

        total_questions = len(questions)

        if total_questions == 0:

            await update.message.reply_text("⚠️ CSV file is empty or invalid.")

            return ConversationHandler.END

        if total_questions > 100:

            questions = questions[:100]

            await update.message.reply_text(

                f"⚠️ CSV contains {total_questions} MCQs. Bot will only upload first 60 due to Telegram limits."

            )

        else:

            await update.message.reply_text(f"✅ CSV upload successful. {total_questions} MCQs detected.")

        context.user_data['questions'] = questions

        keyboard = [

            [InlineKeyboardButton("Bot", callback_data='bot')],

            [InlineKeyboardButton("Channel", callback_data='channel')]

        ]

        await update.message.reply_text(

            "Do you want to upload these quizzes to the bot or forward them to a channel?",

            reply_markup=InlineKeyboardMarkup(keyboard)

        )

        return CHOOSE_DESTINATION

    except Exception as e:

        logging.error(f"Error processing CSV file: {e}")

        await update.message.reply_text("❌ Failed to process CSV file.")

        return ConversationHandler.END

# -------------------------------

# Flood-safe message sending

# -------------------------------

async def send_message_with_retry(bot, chat_id, text):

    try:

        await bot.send_message(chat_id=chat_id, text=text)

    except RetryAfter as e:

        await asyncio.sleep(e.retry_after)

        await send_message_with_retry(bot, chat_id, text)

# -------------------------------

# Send polls in batches

# -------------------------------

async def send_all_polls(chat_id, context, questions):

    for q in questions:

        try:

            question_text = q.get("Question", "Untitled Question")

            options = [q.get("Option A", ""), q.get("Option B", ""), q.get("Option C", ""), q.get("Option D", "")]

            await context.bot.send_poll(chat_id, question=question_text, options=options, is_anonymous=False)

            await asyncio.sleep(2)

        except RetryAfter as e:

            await asyncio.sleep(e.retry_after)

        except Exception as e:

            logging.error(f"Error sending poll: {e}")

# -------------------------------

# Choose Destination (bot or channel)

# -------------------------------

async def choose_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    choice = query.data

    questions = context.user_data.get('questions', [])

    if choice == 'bot':

        chat_id = query.message.chat_id

        total_polls = len(questions)

        batch_size = 19

        sent_polls = 0

        for i in range(0, total_polls, batch_size):

            batch = questions[i:i + batch_size]

            await send_all_polls(chat_id, context, batch)

            sent_polls += len(batch)

            await send_message_with_retry(context.bot, chat_id, f"{sent_polls} polls sent to bot.")

            if i + batch_size < total_polls:

                await asyncio.sleep(45)

        await send_message_with_retry(context.bot, chat_id, f"Total of {sent_polls} quizzes sent to bot.")

        return ConversationHandler.END

    elif choice == 'channel':

        user_info = users_collection.find_one({'user_id': user_id})

        if 'channels' not in user_info or not user_info['channels']:

            await query.edit_message_text("⚠️ No channels found. Use /setchannel first.")

            return ConversationHandler.END

        if len(user_info['channels']) == 1:

            channel_id = user_info['channels'][0]

            total_polls = len(questions)

            batch_size = 19

            sent_polls = 0

            for i in range(0, total_polls, batch_size):

                batch = questions[i:i + batch_size]

                await send_all_polls(channel_id, context, batch)

                sent_polls += len(batch)

                await send_message_with_retry(context.bot, channel_id, f"{sent_polls} polls sent to channel {channel_id}.")

                if i + batch_size < total_polls:

                    await asyncio.sleep(45)

            await send_message_with_retry(context.bot, channel_id, f"Total of {sent_polls} quizzes sent to channel {channel_id}.")

            return ConversationHandler.END

        else:

            keyboard = [[InlineKeyboardButton(ch, callback_data=ch)] for ch in user_info['channels']]

            await query.edit_message_text("Choose a channel:", reply_markup=InlineKeyboardMarkup(keyboard))

            return CHOOSE_CHANNEL

# -------------------------------

# Channel selection callback

# -------------------------------

async def channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    channel_id = query.data

    questions = context.user_data.get('questions', [])

    total_polls = len(questions)

    batch_size = 19

    sent_polls = 0

    for i in range(0, total_polls, batch_size):

        batch = questions[i:i + batch_size]

        await send_all_polls(channel_id, context, batch)

        sent_polls += len(batch)

        await send_message_with_retry(context.bot, channel_id, f"{sent_polls} polls sent to {channel_id}.")

        if i + batch_size < total_polls:

            await asyncio.sleep(30)

    await send_message_with_retry(context.bot, channel_id, f"Total of {sent_polls} quizzes sent to {channel_id}.")

    return ConversationHandler.END

# -------------------------------

# Conversation Handler Setup

# -------------------------------

upload_csv_handler = ConversationHandler(

    entry_points=[CommandHandler("uploadcsv", upload_csv_command)],

    states={

        UPLOAD_CSV: [CallbackQueryHandler(handle_upload_choice)],

        COLLECT_TEXT: [

            MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text_csv),

            CommandHandler("done", done_collecting)

        ],

        CHOOSE_DESTINATION: [CallbackQueryHandler(choose_destination)],

        CHOOSE_CHANNEL: [CallbackQueryHandler(channel_callback)],

    },

    fallbacks=[],

)
