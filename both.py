# Telegram AI Quiz Bot â€” one-file implementation

# Features

# - /aiquiz: User side hierarchical navigation (Subject â†’ Sub-Subject â†’ Topic â†’ Test) to run a 20-MCQ quiz from stored CSVs

# - /addaicsv (Admin only): Single interactive command to add Subjects/Sub-Subjects/Topics and upload CSVs as Tests

# - Reuses common CSV â†’ MCQ sender (send_mcqs_from_csv). Adjust to match your existing CSV format if needed.

#

# Requirements

#   pip install python-telegram-bot==20.7

#   Python 3.10+

# Environment

#   export BOT_TOKEN="<your-bot-token>"

# Optional settings inside the code below: ADMIN_IDS, QUIZ_ROOT, ALLOW_TEXT_MODE

from __future__ import annotations

import asyncio

import csv

import logging

import os

import re

from dataclasses import dataclass

from pathlib import Path

from typing import List, Tuple, Optional

from telegram import (

    Update,

    InlineKeyboardButton,

    InlineKeyboardMarkup,

    InputFile,

)

from telegram.constants import ChatAction, ParseMode

from telegram.ext import (

    Application,

    ApplicationBuilder,

    CommandHandler,

    ContextTypes,

    ConversationHandler,

    CallbackQueryHandler,

    MessageHandler,

    filters,

)




# ---------------------- CONFIG ----------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "7712967452:AAH-pB8BxHKk-ywX8kX0Kco3sJzaFrkPiyA")

# Admin user IDs who can use /addaicsv

ADMIN_IDS = {7154097545}  # <- replace with your Telegram numeric user IDs

# Folder where quizzes are stored in Subject/SubSubject/Topic/TestN.csv hierarchy

QUIZ_ROOT = Path("quizzes")

QUIZ_ROOT.mkdir(parents=True, exist_ok=True)

# If True, also send each question once as plain text after the poll with the correct answer/explanation

# (Handy for study channels that prefer text logs). Leave False to only send polls.

ALLOW_TEXT_MODE = False

# Expected CSV columns (order flexible but names should match)

EXPECTED_COLUMNS = [

    "Question", "Option A", "Option B", "Option C", "Option D", "Answer", "Description"

]

# ---------------------- LOGGING ----------------------

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",

)

logger = logging.getLogger("ai_quiz_bot")

# ---------------------- DATA HELPERS ----------------------

def sanitize_name(name: str) -> str:

    """Filesystem-safe folder/file name from a human label."""

    name = name.strip()

    name = re.sub(r"\s+", " ", name)  # collapse internal spaces

    safe = re.sub(r"[^A-Za-z0-9 _\-]", "", name)

    return safe.strip().replace(" ", "_")

def list_subjects() -> List[str]:

    return sorted([p.name for p in QUIZ_ROOT.iterdir() if p.is_dir()])

def list_subsubjects(subject: str) -> List[str]:

    base = QUIZ_ROOT / subject

    if not base.exists():

        return []

    return sorted([p.name for p in base.iterdir() if p.is_dir()])

def list_topics(subject: str, subsubject: str) -> List[str]:

    base = QUIZ_ROOT / subject / subsubject

    if not base.exists():

        return []

    return sorted([p.name for p in base.iterdir() if p.is_dir()])

def list_tests(subject: str, subsubject: str, topic: str) -> List[str]:

    base = QUIZ_ROOT / subject / subsubject / topic

    if not base.exists():

        return []

    return sorted([p.stem for p in base.glob("*.csv")])

def ensure_path(subject: str, subsubject: Optional[str] = None, topic: Optional[str] = None) -> Path:

    p = QUIZ_ROOT / subject

    if subsubject:

        p = p / subsubject

    if topic:

        p = p / topic

    p.mkdir(parents=True, exist_ok=True)

    return p

def next_test_name(subject: str, subsubject: str, topic: str) -> str:

    # Determine next available Test number based on existing CSV files

    existing = list_tests(subject, subsubject, topic)

    nums = []

    for t in existing:

        m = re.search(r"(\d+)$", t)

        if m:

            nums.append(int(m.group(1)))

    n = max(nums) + 1 if nums else 1

    return f"Test_{n}"

# ---------------------- CSV PARSER ----------------------

@dataclass

class MCQ:

    question: str

    options: List[str]

    correct_index: int  # 0..3

    description: str

def parse_csv(file_path: Path) -> List[MCQ]:

    """Parse CSV to a list of MCQ. Expects columns like EXPECTED_COLUMNS.

    Accepts Answer either as A/B/C/D or 1/2/3/4."""

    rows: List[MCQ] = []

    with file_path.open("r", encoding="utf-8-sig") as f:

        reader = csv.DictReader(f)

        headers = [h.strip() for h in reader.fieldnames or []]

        missing = [c for c in EXPECTED_COLUMNS if c not in headers]

        if missing:

            raise ValueError(f"CSV missing columns: {missing}; got {headers}")

        for i, r in enumerate(reader, start=1):

            q = (r.get("Question") or "").strip()

            opts = [

                (r.get("Option A") or "").strip(),

                (r.get("Option B") or "").strip(),

                (r.get("Option C") or "").strip(),

                (r.get("Option D") or "").strip(),

            ]

            ans_raw = (r.get("Answer") or "").strip().upper()

            desc = (r.get("Description") or "").strip()

            if not q or any(o == "" for o in opts) or not ans_raw:

                logger.warning("Skipping row %s due to empties", i)

                continue

            if ans_raw in {"A", "B", "C", "D"}:

                idx = {"A": 0, "B": 1, "C": 2, "D": 3}[ans_raw]

            else:

                try:

                    idx = int(ans_raw) - 1

                except Exception:

                    raise ValueError(f"Bad Answer in row {i}: {ans_raw}")

            if idx not in (0, 1, 2, 3):

                raise ValueError(f"Answer index out of range in row {i}: {ans_raw}")

            rows.append(MCQ(q, opts, idx, desc))

    return rows

# ---------------------- QUIZ SENDER ----------------------


# ---- MCQ Sending Function ----
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# 🔹 User-wise quiz session store
user_quiz_sessions = {}


# ========================
# 1. Function to send MCQs
# ========================
async def send_mcqs_from_csv(update: Update, context: ContextTypes.DEFAULT_TYPE, mcqs: list):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Session create
    user_quiz_sessions[user_id] = {
        "total": len(mcqs),
        "correct": 0,
        "pending_polls": set(),
        "result_message_id": None
    }

    # Send all polls
    for idx, mcq in enumerate(mcqs, start=1):
        question = f"Q{idx}. {mcq['Question']}"
        options = [mcq["Option A"], mcq["Option B"], mcq["Option C"], mcq["Option D"]]

        poll_message = await context.bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=options,
            type="quiz",
            correct_option_id=ord(mcq["Answer"].upper()) - 65,  # A=0, B=1, C=2, D=3
            is_anonymous=False,
            explanation=mcq.get("Description", "")
        )

        # Save poll id for tracking
        user_quiz_sessions[user_id]["pending_polls"].add(poll_message.poll.id)

    # 🔹 Last message as placeholder
    result_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="⚠️ कृपया पहले सभी MCQ attempt करें। जब आप पूरे complete कर लेंगे, यहाँ आपका score दिखाया जाएगा।"
    )

    # Save result message id
    user_quiz_sessions[user_id]["result_message_id"] = result_msg.message_id



# ========================
# 2. Poll Handler
# ========================
async def poll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.poll

    # Find which user session this poll belongs to
    for user_id, session in user_quiz_sessions.items():
        if poll.id in session["pending_polls"]:
            # Remove from pending
            session["pending_polls"].discard(poll.id)

            # ✅ Check if answer is correct
            for option in poll.options:
                if option.voter_count > 0 and option.correct:  # user selected correct one
                    session["correct"] += 1
                    break

            # If all polls attempted
            if not session["pending_polls"]:
                chat_id = update.effective_chat.id if update.effective_chat else None
                if chat_id:
                    # Prepare final text
                    result_text = f"✅ आपने सभी {session['total']} प्रश्न attempt कर लिए!\n\n" \
                                  f"📊 आपका Score: {session['correct']} / {session['total']}"

                    # Inline button for answers
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📑 Show Answers", callback_data="show_answers")]
                    ])

                    # Update the placeholder message
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=session["result_message_id"],
                        text=result_text,
                        reply_markup=keyboard
                    )
            break


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

# ---------------------- ADMIN FLOW: /addaicsv ----------------------

# Conversation states

A_SUBJECT, A_SUBSUB, A_TOPIC, A_TEST, A_ADD_TEXT, A_WAIT_CSV = range(100, 106)

NEW_SUBJECT = "ADD_NEW_SUBJECT"

NEW_SUBSUB = "ADD_NEW_SUBSUB"

NEW_TOPIC = "ADD_NEW_TOPIC"

NEW_TEST = "ADD_NEW_TEST"

BACK = "BACK"

CANCEL = "CANCEL"

def is_admin(update: Update) -> bool:

    uid = update.effective_user.id if update.effective_user else None

    return uid in ADMIN_IDS

def kb_rows(items: List[Tuple[str, str]], extra: Optional[List[Tuple[str, str]]] = None) -> InlineKeyboardMarkup:

    buttons = [[InlineKeyboardButton(text, callback_data=data)] for text, data in items]

    if extra:

        buttons += [[InlineKeyboardButton(text, callback_data=data)] for text, data in extra]

    return InlineKeyboardMarkup(buttons)

def subject_keyboard() -> InlineKeyboardMarkup:

    items = [(s.replace("_", " "), f"S|{s}") for s in list_subjects()]

    extra = [("âž• Add New Subject", NEW_SUBJECT)]

    return kb_rows(items, extra)

def subsubject_keyboard(subject: str) -> InlineKeyboardMarkup:

    items = [(ss.replace("_", " "), f"SS|{subject}|{ss}") for ss in list_subsubjects(subject)]

    extra = [("â†©ï¸ Back", BACK), ("âž• Add New Sub-Subject", NEW_SUBSUB)]

    return kb_rows(items, extra)

def topic_keyboard(subject: str, sub: str) -> InlineKeyboardMarkup:

    items = [(t.replace("_", " "), f"T|{subject}|{sub}|{t}") for t in list_topics(subject, sub)]

    extra = [("â†©ï¸ Back", BACK), ("âž• Add New Topic", NEW_TOPIC)]

    return kb_rows(items, extra)

def test_keyboard(subject: str, sub: str, topic: str) -> InlineKeyboardMarkup:

    items = [(x.replace("_", " "), f"TE|{subject}|{sub}|{topic}|{x}") for x in list_tests(subject, sub, topic)]

    extra = [("â†©ï¸ Back", BACK), ("âž• Add New Test (Upload CSV)", NEW_TEST)]

    return kb_rows(items, extra)

async def addaicsv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update):

        return await update.effective_message.reply_text("ðŸ” Admins only.")

    context.user_data.clear()

    await update.effective_message.reply_text("ðŸ“ Select Subject:", reply_markup=subject_keyboard())

    return A_SUBJECT

async def addaicsv_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    # state memory

    subj = context.user_data.get("subject")

    subsub = context.user_data.get("subsubject")

    topic = context.user_data.get("topic")

    if data == NEW_SUBJECT:

        context.user_data["awaiting"] = "subject"

        await query.edit_message_text("âœï¸ Enter new Subject name:")

        return A_ADD_TEXT

    if data == NEW_SUBSUB:

        context.user_data["awaiting"] = "subsubject"

        await query.edit_message_text(f"âœï¸ Enter new Sub-Subject name for <b>{subj}</b>:", parse_mode=ParseMode.HTML)

        return A_ADD_TEXT

    if data == NEW_TOPIC:

        context.user_data["awaiting"] = "topic"

        await query.edit_message_text(

            f"âœï¸ Enter new Topic name for <b>{subj}</b> â†’ <b>{subsub}</b>:", parse_mode=ParseMode.HTML

        )

        return A_ADD_TEXT

    if data == NEW_TEST:

        # Prompt for CSV upload

        await query.edit_message_text(

            f"ðŸ“¤ Upload CSV for: <b>{subj}</b> â†’ <b>{subsub}</b> â†’ <b>{topic}</b>\n"

            f"(It will be saved as next TestN.csv)",

            parse_mode=ParseMode.HTML,

        )

        return A_WAIT_CSV

    if data == BACK:

        # step back logically

        if topic:

            context.user_data.pop("topic", None)

            await query.edit_message_text(

                f"ðŸ“‚ Select Topic under <b>{subj}</b> â†’ <b>{subsub}</b>:",

                parse_mode=ParseMode.HTML,

                reply_markup=topic_keyboard(subj, subsub),

            )

            return A_TOPIC

        if subsub:

            context.user_data.pop("subsubject", None)

            await query.edit_message_text(

                f"ðŸ“ Select Sub-Subject under <b>{subj}</b>:",

                parse_mode=ParseMode.HTML,

                reply_markup=subsubject_keyboard(subj),

            )

            return A_SUBSUB

        if subj:

            context.user_data.pop("subject", None)

        await query.edit_message_text("ðŸ“ Select Subject:", reply_markup=subject_keyboard())

        return A_SUBJECT

    # normal selections

    if data.startswith("S|"):

        _, s = data.split("|", 1)

        context.user_data["subject"] = s

        await query.edit_message_text(

            f"ðŸ“ Subject: <b>{s.replace('_',' ')}</b>\nSelect Sub-Subject:",

            parse_mode=ParseMode.HTML,

            reply_markup=subsubject_keyboard(s),

        )

        return A_SUBSUB

    if data.startswith("SS|"):

        _, s, ss = data.split("|", 2)

        context.user_data["subject"] = s

        context.user_data["subsubject"] = ss

        await query.edit_message_text(

            f"ðŸ“‚ {s.replace('_',' ')} â†’ <b>{ss.replace('_',' ')}</b>\nSelect Topic:",

            parse_mode=ParseMode.HTML,

            reply_markup=topic_keyboard(s, ss),

        )

        return A_TOPIC

    if data.startswith("T|"):

        _, s, ss, t = data.split("|", 3)

        context.user_data["subject"] = s

        context.user_data["subsubject"] = ss

        context.user_data["topic"] = t

        await query.edit_message_text(

            f"ðŸ“š {s.replace('_',' ')} â†’ {ss.replace('_',' ')} â†’ <b>{t.replace('_',' ')}</b>\nSelect Test:",

            parse_mode=ParseMode.HTML,

            reply_markup=test_keyboard(s, ss, t),

        )

        return A_TEST

    if data.startswith("TE|"):

        # Existing test selected -> offer to replace CSV

        _, s, ss, t, test = data.split("|", 4)

        context.user_data.update({"subject": s, "subsubject": ss, "topic": t, "test": test})

        await query.edit_message_text(

            f"ðŸ—‚ Selected: <b>{s}</b> â†’ <b>{ss}</b> â†’ <b>{t}</b> â†’ <b>{test}</b>\n"

            f"Send a new CSV to replace/update this test, or tap â†©ï¸ Back.",

            parse_mode=ParseMode.HTML,

            reply_markup=kb_rows([], [("â†©ï¸ Back", BACK)]),

        )

        return A_WAIT_CSV

    # Fallback

    await query.edit_message_text("Unknown action. Starting overâ€¦", reply_markup=subject_keyboard())

    return A_SUBJECT

async def addaicsv_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Handles text replies for adding Subject/Sub-Subject/Topic

    if not is_admin(update):

        return

    awaiting = context.user_data.get("awaiting")

    raw = (update.effective_message.text or "").strip()

    if not raw:

        return

    safe = sanitize_name(raw)

    subj = context.user_data.get("subject")

    subsub = context.user_data.get("subsubject")

    if awaiting == "subject":

        ensure_path(safe)

        context.user_data["subject"] = safe

        context.user_data.pop("awaiting", None)

        await update.effective_message.reply_text(

            f"âœ… Subject added: <b>{safe.replace('_',' ')}</b>\nSelect Sub-Subject:",

            parse_mode=ParseMode.HTML,

            reply_markup=subsubject_keyboard(safe),

        )

        return A_SUBSUB

    if awaiting == "subsubject":

        ensure_path(subj, safe)

        context.user_data["subsubject"] = safe

        context.user_data.pop("awaiting", None)

        await update.effective_message.reply_text(

            f"âœ… Sub-Subject added under <b>{subj.replace('_',' ')}</b>: <b>{safe.replace('_',' ')}</b>\nSelect Topic:",

            parse_mode=ParseMode.HTML,

            reply_markup=topic_keyboard(subj, safe),

        )

        return A_TOPIC

    if awaiting == "topic":

        ensure_path(subj, subsub, safe)

        context.user_data["topic"] = safe

        context.user_data.pop("awaiting", None)

        await update.effective_message.reply_text(

            f"âœ… Topic added: <b>{safe.replace('_',' ')}</b>\nSelect Test:",

            parse_mode=ParseMode.HTML,

            reply_markup=test_keyboard(subj, subsub, safe),

        )

        return A_TEST

    # If not awaiting anything, ignore

async def addaicsv_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Accept CSV upload and save to appropriate path

    if not is_admin(update):

        return

    doc = update.effective_message.document

    if not doc or not doc.file_name.lower().endswith(".csv"):

        await update.effective_message.reply_text("â— Please upload a .csv file.")

        return

    subj = context.user_data.get("subject")

    subsub = context.user_data.get("subsubject")

    topic = context.user_data.get("topic")

    existing_test = context.user_data.get("test")  # if replacing

    if not (subj and subsub and topic):

        await update.effective_message.reply_text("Context lost. Please run /addaicsv again.")

        return ConversationHandler.END

    base = ensure_path(subj, subsub, topic)

    if existing_test:

        test_name = existing_test

    else:

        test_name = next_test_name(subj, subsub, topic)

    dest = base / f"{test_name}.csv"

    file = await doc.get_file()

    await file.download_to_drive(custom_path=str(dest))

    # Quick validation

    try:

        _ = parse_csv(dest)

    except Exception as e:

        dest.unlink(missing_ok=True)

        await update.effective_message.reply_text(f"âŒ CSV invalid: {e}")

        return

    await update.effective_message.reply_text(

        f"âœ… CSV saved as: <b>{subj}</b> â†’ <b>{subsub}</b> â†’ <b>{topic}</b> â†’ <b>{test_name}</b>",

        parse_mode=ParseMode.HTML,

        reply_markup=test_keyboard(subj, subsub, topic),

    )

    # Clear replacement flag so next upload creates a new Test

    context.user_data.pop("test", None)

    return A_TEST

async def addaicsv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.effective_message.reply_text("âŽ Admin flow cancelled.")

    return ConversationHandler.END

# ---------------------- USER FLOW: /aiquiz ----------------------

U_SUBJECT, U_SUBSUB, U_TOPIC, U_TEST = range(200, 204)

def u_subject_keyboard() -> InlineKeyboardMarkup:

    items = [(s.replace("_", " "), f"US|{s}") for s in list_subjects()]

    return kb_rows(items)

def u_subsubject_keyboard(s: str) -> InlineKeyboardMarkup:

    items = [(x.replace("_", " "), f"USS|{s}|{x}") for x in list_subsubjects(s)]

    extra = [("â†©ï¸ Back", BACK)]

    return kb_rows(items, extra)

def u_topic_keyboard(s: str, ss: str) -> InlineKeyboardMarkup:

    items = [(x.replace("_", " "), f"UT|{s}|{ss}|{x}") for x in list_topics(s, ss)]

    extra = [("â†©ï¸ Back", BACK)]

    return kb_rows(items, extra)

def u_test_keyboard(s: str, ss: str, t: str) -> InlineKeyboardMarkup:

    tests = list_tests(s, ss, t)

    label_items = []

    for test in tests:

        # optionally show (20 MCQ) if you want

        label_items.append((test.replace("_", " "), f"UTE|{s}|{ss}|{t}|{test}"))

    extra = [("â†©ï¸ Back", BACK)]

    return kb_rows(label_items, extra)

async def aiquiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not list_subjects():

        await update.effective_message.reply_text("ðŸ“­ No quizzes available yet. Please try later.")

        return ConversationHandler.END

    await update.effective_message.reply_text("ðŸŽ¯ Choose Subject:", reply_markup=u_subject_keyboard())

    return U_SUBJECT

async def aiquiz_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    subj = context.user_data.get("u_subject")

    subsub = context.user_data.get("u_subsubject")

    topic = context.user_data.get("u_topic")

    if data == BACK:

        if topic:

            context.user_data.pop("u_topic", None)

            await query.edit_message_text(

                f"ðŸ“š {subj.replace('_',' ')} â†’ {subsub.replace('_',' ')}\nChoose Topic:",

                reply_markup=u_topic_keyboard(subj, subsub),

            )

            return U_TOPIC

        if subsub:

            context.user_data.pop("u_subsubject", None)

            await query.edit_message_text(

                f"ðŸ“ {subj.replace('_',' ')}\nChoose Sub-Subject:", reply_markup=u_subsubject_keyboard(subj)

            )

            return U_SUBSUB

        if subj:

            context.user_data.pop("u_subject", None)

        await query.edit_message_text("ðŸŽ¯ Choose Subject:", reply_markup=u_subject_keyboard())

        return U_SUBJECT

    if data.startswith("US|"):

        _, s = data.split("|", 1)

        context.user_data["u_subject"] = s

        if not list_subsubjects(s):

            await query.edit_message_text("No sub-subjects available here.")

            return ConversationHandler.END

        await query.edit_message_text(

            f"ðŸ“ {s.replace('_',' ')}\nChoose Sub-Subject:", reply_markup=u_subsubject_keyboard(s)

        )

        return U_SUBSUB

    if data.startswith("USS|"):

        _, s, ss = data.split("|", 2)

        context.user_data["u_subject"] = s

        context.user_data["u_subsubject"] = ss

        if not list_topics(s, ss):

            await query.edit_message_text("No topics here yet.")

            return ConversationHandler.END

        await query.edit_message_text(

            f"ðŸ“‚ {s.replace('_',' ')} â†’ {ss.replace('_',' ')}\nChoose Topic:",

            reply_markup=u_topic_keyboard(s, ss),

        )

        return U_TOPIC

    if data.startswith("UT|"):

        _, s, ss, t = data.split("|", 3)

        context.user_data.update({"u_subject": s, "u_subsubject": ss, "u_topic": t})

        if not list_tests(s, ss, t):

            await query.edit_message_text("No tests here yet.")

            return ConversationHandler.END

        await query.edit_message_text(

            f"ðŸ“š {s.replace('_',' ')} â†’ {ss.replace('_',' ')} â†’ {t.replace('_',' ')}\nChoose Test:",

            reply_markup=u_test_keyboard(s, ss, t),

        )

        return U_TEST

    if data.startswith("UTE|"):

        _, s, ss, t, test = data.split("|", 4)

        csv_path = QUIZ_ROOT / s / ss / t / f"{test}.csv"

        await query.edit_message_text(

            f"â–¶ï¸ Starting: <b>{s.replace('_',' ')}</b> â†’ <b>{ss.replace('_',' ')}</b> â†’ "

            f"<b>{t.replace('_',' ')}</b> â†’ <b>{test.replace('_',' ')}</b>",

            parse_mode=ParseMode.HTML,

        )

        await send_mcqs_from_csv(update, context, csv_path)

        return ConversationHandler.END

    await query.edit_message_text("Unknown option. Please run /aiquiz again.")

    return ConversationHandler.END

async def cancel_common(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.effective_message.reply_text("âŽ Cancelled.")

    return ConversationHandler.END

# ---------------------- /start ----------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.effective_message.reply_text(

        """

ðŸ‘‹ Welcome to AI Quiz Bot!

User:

/aiquiz â€” Attempt quizzes by navigating Subject â†’ Topic â†’ Test

Admin:

/addaicsv â€” Add Subjects/Sub-Subjects/Topics and upload CSVs as Tests

Tip: CSV columns â†’ "Question, Option A, Option B, Option C, Option D, Answer, Description"

        """.strip()

    )

# ---------------------- APPLICATION ----------------------
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # Admin conversation
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("addaicsv", addaicsv_start)],
        states={
            A_SUBJECT: [CallbackQueryHandler(addaicsv_cb)],
            A_SUBSUB: [CallbackQueryHandler(addaicsv_cb)],
            A_TOPIC: [CallbackQueryHandler(addaicsv_cb)],
            A_TEST: [CallbackQueryHandler(addaicsv_cb)],
            A_ADD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addaicsv_text)],
            A_WAIT_CSV: [MessageHandler(filters.Document.MimeType("text/csv") | filters.Document.FileExtension("csv"), addaicsv_csv)],
        },
        fallbacks=[CommandHandler("cancel", addaicsv_cancel)],
        name="admin_addaicsv",
        persistent=False,
        allow_reentry=True,
    )

    # User conversation
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("aiquiz", aiquiz_start)],
        states={
            U_SUBJECT: [CallbackQueryHandler(aiquiz_cb)],
            U_SUBSUB: [CallbackQueryHandler(aiquiz_cb)],
            U_TOPIC: [CallbackQueryHandler(aiquiz_cb)],
            U_TEST: [CallbackQueryHandler(aiquiz_cb)],
        },
        fallbacks=[CommandHandler("cancel", cancel_common)],
        name="user_aiquiz",
        persistent=False,
        allow_reentry=True,
    )

    # ✅ Sab handlers yahin add karo
    app.add_handler(CallbackQueryHandler(show_answers_callback, pattern="^show_answers$"))
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(admin_conv)
    app.add_handler(user_conv)

    return app


if __name__ == "__main__":
    if BOT_TOKEN == "PUT-YOUR-TOKEN-HERE" or not BOT_TOKEN:
        raise SystemExit("Please set BOT_TOKEN env var.")

    application = build_app()
    application.run_polling(close_loop=False)

