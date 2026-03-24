import csv
import json
import os
import tempfile
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Document,
    Poll
)
from telegram.ext import (
    Application,
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

# ================== 🔑 BOT TOKEN ==================
BOT_TOKEN = "7596059729:AAEmS1oaJLHn51IgUrkV2ggCCgksBmSFjzM"   # 👈 yaha apna token daalo

# ================== DUMMY AUTH ==================
async def is_user_authorized(user_id: int) -> bool:
    return True  # test ke liye sab allowed

# ================= STATES =================
ASK_NEGATIVE, ASK_TESTNAME, COLLECTING = range(3)

# ================= CONFIG =================
TEMPLATE_FILE = "template.html"

DEFAULT_DESCRIPTION = ""

def get_description_for_chat_id(context, chat_id):
    return ""

# ================= ENTRY =================
async def csv2html_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["html_quiz"] = {"questions": []}

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("0", callback_data="neg_0"),
            InlineKeyboardButton("0.25", callback_data="neg_0.25"),
        ],
        [
            InlineKeyboardButton("0.33", callback_data="neg_0.33"),
            InlineKeyboardButton("0.50", callback_data="neg_0.50"),
        ],
    ])

    await update.message.reply_text(
        "🧮 Negative marking select karo 👇",
        reply_markup=kb
    )
    return ASK_NEGATIVE

# ================= NEGATIVE =================
async def negative_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    neg = float(query.data.replace("neg_", ""))
    context.user_data["html_quiz"]["negative"] = neg

    await query.message.edit_text(
        f"✅ Negative marking set: {neg}\n\n📝 Test ka naam bhejo"
    )
    return ASK_TESTNAME

# ================= TEST NAME =================
async def testname_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["html_quiz"]["title"] = update.message.text.strip()

    await update.message.reply_text(
        "📥 CSV / TXT / Quiz Poll bhejo\n\nFinish: /done"
    )
    return COLLECTING

# ================= CSV =================
async def handle_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document

    file = await doc.get_file()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    await file.download_to_drive(tmp.name)

    with open(tmp.name, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            context.user_data["html_quiz"]["questions"].append(
                build_question(
                    row["Question"],
                    [row["Option A"], row["Option B"], row["Option C"], row["Option D"]],
                    row["Answer"],
                    row.get("Description", ""),
                    context
                )
            )

    os.unlink(tmp.name)
    await update.message.reply_text("✅ CSV added")

# ================= POLL =================
async def handle_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll: Poll = update.message.poll

    context.user_data["html_quiz"]["questions"].append(
        build_question(
            poll.question,
            [o.text for o in poll.options],
            chr(65 + poll.correct_option_id),
            poll.explanation or "",
            context
        )
    )

    await update.message.reply_text("✅ Poll added")

# ================= TXT =================
async def handle_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document

    file = await doc.get_file()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    await file.download_to_drive(tmp.name)

    with open(tmp.name, encoding="utf-8") as f:
        blocks = f.read().split("\n\n")
        for b in blocks:
            lines = [l.strip() for l in b.split("\n") if l.strip()]
            if len(lines) < 6:
                continue

            context.user_data["html_quiz"]["questions"].append(
                build_question(
                    lines[0],
                    lines[1:5],
                    lines[5].replace("Answer:", "").strip(),
                    "",
                    context
                )
            )

    os.unlink(tmp.name)
    await update.message.reply_text("✅ TXT added")

# ================= DONE =================
async def done_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data["html_quiz"]

    html = generate_html(data["questions"], data["title"])

    path = tempfile.NamedTemporaryFile(delete=False, suffix=".html").name
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    await update.message.reply_document(
        document=open(path, "rb"),
        filename=f"{data['title']}.html"
    )

    os.unlink(path)
    return ConversationHandler.END

# ================= HELPERS =================
def build_question(q, opts, ans, desc, context):
    neg = context.user_data["html_quiz"]["negative"]

    return {
        "id": str(len(context.user_data["html_quiz"]["questions"])),
        "question": q,
        "option_1": opts[0],
        "option_2": opts[1],
        "option_3": opts[2],
        "option_4": opts[3],
        "answer": {"A": "1", "B": "2", "C": "3", "D": "4"}.get(ans.upper(), "1"),
        "solution_text": desc,
        "positive_marks": "1.00",
        "negative_marks": str(neg),
    }

def generate_html(questions, title):
    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        tpl = f.read()

    return tpl.replace("{{QUESTIONS_DATA}}", json.dumps(questions)).replace("{{QUIZ_TITLE}}", title)

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("csv2html", csv2html_start)],
        states={
            ASK_NEGATIVE: [CallbackQueryHandler(negative_callback)],
            ASK_TESTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, testname_handler)],
            COLLECTING: [
                MessageHandler(filters.Document.ALL, handle_csv),
                MessageHandler(filters.POLL, handle_poll),
                CommandHandler("done", done_handler),
            ],
        },
        fallbacks=[CommandHandler("done", done_handler)],
    )

    app.add_handler(conv)

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
