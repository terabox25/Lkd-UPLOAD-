import asyncio
import logging
from pathlib import Path
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ContextTypes, CallbackQueryHandler

from helpers.csv_parser import parse_csv

logger = logging.getLogger(__name__)

# ---- MCQ Sending Function ----
async def send_mcqs_from_csv(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    csv_path: Path,
    destination_chat_id: Optional[int] = None,
) -> None:
    chat_id = destination_chat_id or (update.effective_chat.id if update.effective_chat else None)
    if chat_id is None:
        return

    try:
        mcqs = parse_csv(csv_path)
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ CSV error: {e}", protect_content=True)
        return

    if not mcqs:
        await context.bot.send_message(chat_id=chat_id, text="CSV me koi valid MCQ nahi mila.", protect_content=True)
        return

    # Save MCQs in user_data for later use
    context.user_data["last_mcqs"] = mcqs

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"▶️ Starting quiz from: <b>{csv_path.stem}</b>",
        parse_mode=ParseMode.HTML,
        protect_content=True,
    )

    limit = min(20, len(mcqs))
    for i in range(limit):
        m = mcqs[i]
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await context.bot.send_poll(
                chat_id=chat_id,
                question=f"Q{i+1}. {m.question}",
                options=m.options,
                type="quiz",
                correct_option_id=m.correct_index,
                is_anonymous=False,
                explanation=m.description[:200],
                allows_multiple_answers=False,
                protect_content=True,
            )
        except Exception as e:
            logger.exception("Failed to send poll %s: %s", i + 1, e)
        await asyncio.sleep(1.2)

    # Send quiz complete with button
    keyboard = [[InlineKeyboardButton("📑 Show Answers", callback_data="show_answers")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Quiz complete. Keep practicing!",
        reply_markup=reply_markup,
        protect_content=True,
    )


# ---- Callback Handler ----
async def show_answers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    mcqs = context.user_data.get("last_mcqs")
    if not mcqs:
        await query.message.reply_text("❌ No MCQs found to show answers.", protect_content=True)
        return

    # Prepare formatted text
    text_blocks = []
    for i, m in enumerate(mcqs[:20], start=1):
        ans_letter = "ABCD"[m.correct_index]
        text_blocks.append(
            f"<b>Q{i}.</b> {m.question}\n"
            f"A) {m.options[0]}\nB) {m.options[1]}\nC) {m.options[2]}\nD) {m.options[3]}\n"
            f"<b>Answer:</b> {ans_letter}\n"
            f"<i>{m.description}</i>\n"
        )

    final_text = "\n".join(text_blocks)

    await query.message.reply_text(final_text, parse_mode=ParseMode.HTML, protect_content=True)


# Register callback
def register(application):
    application.add_handler(CallbackQueryHandler(show_answers_callback, pattern="^show_answers$"))
