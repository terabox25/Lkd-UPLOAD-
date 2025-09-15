# save as ai_quiz_bot_fixed.py
from __future__ import annotations

import asyncio
import csv
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

# ---------------------- CONFIG ----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")  # set in env
ADMIN_IDS = {7154097545}  # replace
QUIZ_ROOT = Path("quizzes")
QUIZ_ROOT.mkdir(parents=True, exist_ok=True)
ALLOW_TEXT_MODE = False

EXPECTED_COLUMNS = [
    "Question", "Option A", "Option B", "Option C", "Option D", "Answer", "Description"
]

# ---------------------- LOGGING ----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ai_quiz_bot_fixed")

# ---------------------- DATA HELPERS ----------------------
def sanitize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
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
    rows: List[MCQ] = []
    with file_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
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
async def send_mcqs_from_csv(update: Update, context: ContextTypes.DEFAULT_TYPE, csv_path: Path, destination_chat_id: Optional[int] = None):
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

    # store mcqs for this chat (so answers/show-answers can access them)
    context.bot_data.setdefault("mcqs_by_chat", {})[chat_id] = mcqs
    context.bot_data.setdefault("responses_by_chat", {}).setdefault(chat_id, {})
    context.bot_data.setdefault("poll_map", {})

    total_to_send = min(20, len(mcqs))
    context.bot_data["total_mcqs_by_chat"] = context.bot_data.get("total_mcqs_by_chat", {})
    context.bot_data["total_mcqs_by_chat"][chat_id] = total_to_send

    await context.bot.send_message(chat_id=chat_id, text=f"▶️ Starting quiz from: <b>{csv_path.stem}</b>", parse_mode=ParseMode.HTML)

    for i, m in enumerate(mcqs[:total_to_send]):
        try:
            poll_msg = await context.bot.send_poll(
                chat_id=chat_id,
                question=f"Q{i+1}. {m.question}",
                options=m.options,
                type="quiz",
                correct_option_id=m.correct_index,
                is_anonymous=False,
                explanation=None,
                allows_multiple_answers=False,
            )
            # map poll id to chat and index
            context.bot_data["poll_map"][poll_msg.poll.id] = {"chat_id": chat_id, "index": i}
        except Exception as e:
            logger.exception("Failed to send poll %s: %s", i + 1, e)
        await asyncio.sleep(1.2)

# PollAnswer handler
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = answer.user.id
    poll_id = answer.poll_id
    chosen = answer.option_ids  # list

    poll_map = context.bot_data.get("poll_map", {})
    if poll_id not in poll_map:
        # unknown poll (maybe older) — ignore
        return
    info = poll_map[poll_id]
    chat_id = info["chat_id"]
    q_index = info["index"]

    # ensure structures exist
    responses_by_chat = context.bot_data.setdefault("responses_by_chat", {})
    this_chat_responses = responses_by_chat.setdefault(chat_id, {})
    user_responses = this_chat_responses.setdefault(user_id, {})

    user_responses[q_index] = chosen

    total_mcqs = context.bot_data.get("total_mcqs_by_chat", {}).get(chat_id, 0)

    # check completion
    if len(user_responses) >= total_mcqs and total_mcqs > 0:
        # compute score
        mcqs = context.bot_data.get("mcqs_by_chat", {}).get(chat_id, [])
        score = 0
        for idx, m in enumerate(mcqs[:total_mcqs]):
            if user_responses.get(idx) == [m.correct_index]:
                score += 1

        # Send a private message to the user with Show Answers button (scoped to user)
        keyboard = [[InlineKeyboardButton("📑 Show Answers", callback_data=f"show_answers|{user_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Aapka Score: <b>{score}/{total_mcqs}</b>\n\nAb aap Show Answers button dabakar explanations dekh sakte ho.",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except Exception:
            # if bot cannot message user privately (e.g. user hasn't started bot),
            # fall back to sending in the quiz chat but without private scoping.
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ <a href='tg://user?id={user_id}'>User</a> scored <b>{score}/{total_mcqs}</b> (can't DM).",
                parse_mode=ParseMode.HTML,
            )

# Callback to show answers (only allowed when callback_data matches the user id)
async def show_answers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    parts = data.split("|")
    if len(parts) != 2 or parts[0] != "show_answers":
        await query.message.reply_text("Invalid action.")
        return

    owner_id = int(parts[1])
    caller_id = query.from_user.id
    if caller_id != owner_id:
        await query.message.reply_text("🚫 Ye button aapke liye nahi hai.")
        return

    # find which chat this user's responses belong to (search responses_by_chat)
    responses_by_chat = context.bot_data.get("responses_by_chat", {})
    mcqs_by_chat = context.bot_data.get("mcqs_by_chat", {})

    found = False
    for chat_id, users_map in responses_by_chat.items():
        if owner_id in users_map:
            user_responses = users_map[owner_id]
            mcqs = mcqs_by_chat.get(chat_id, [])
            total_mcqs = min(len(mcqs), context.bot_data.get("total_mcqs_by_chat", {}).get(chat_id, len(mcqs)))
            # prepare formatted text
            text_blocks = []
            for i, m in enumerate(mcqs[:total_mcqs], start=1):
                ans_letter = "ABCD"[m.correct_index]
                user_choice = user_responses.get(i - 1)
                if user_choice is None:
                    chosen_text = "No answer"
                else:
                    chosen_text = " & ".join([m.options[idx] for idx in user_choice])
                text_blocks.append(
                    f"<b>Q{i}.</b> {m.question}\n"
                    f"A) {m.options[0]}\nB) {m.options[1]}\nC) {m.options[2]}\nD) {m.options[3]}\n"
                    f"<b>Answer:</b> {ans_letter}\n"
                    f"<b>Your:</b> {chosen_text}\n"
                    f"<i>{m.description}</i>\n"
                )
            final_text = "\n".join(text_blocks)
            # send to the user (private)
            try:
                await send_long_message(context.bot, owner_id, final_text, ParseMode.HTML)
            except Exception:
                # fallback to answering where clicked
                await send_long_message(context.bot, query.message.chat_id, final_text, ParseMode.HTML)
            found = True
            break

    if not found:
        await query.message.reply_text("No responses found for you (maybe your answers weren't recorded).")

# ---------------------- ADMIN FLOW: /addaicsv ----------------------
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

def kb_rows(items, extra=None):
    buttons = [[InlineKeyboardButton(text, callback_data=data)] for text, data in items]
    if extra:
        buttons += [[InlineKeyboardButton(text, callback_data=data)] for text, data in extra]
    return InlineKeyboardMarkup(buttons)

def subject_keyboard() -> InlineKeyboardMarkup:
    items = [(s.replace("_", " "), f"S|{s}") for s in list_subjects()]
    extra = [("➕ Add New Subject", NEW_SUBJECT)]
    return kb_rows(items, extra)

def subsubject_keyboard(subject: str) -> InlineKeyboardMarkup:
    items = [(ss.replace("_", " "), f"SS|{subject}|{ss}") for ss in list_subsubjects(subject)]
    extra = [("◀️ Back", BACK), ("➕ Add New Sub-Subject", NEW_SUBSUB)]
    return kb_rows(items, extra)

def topic_keyboard(subject: str, sub: str) -> InlineKeyboardMarkup:
    items = [(t.replace("_", " "), f"T|{subject}|{sub}|{t}") for t in list_topics(subject, sub)]
    extra = [("◀️ Back", BACK), ("➕ Add New Topic", NEW_TOPIC)]
    return kb_rows(items, extra)

def test_keyboard(subject: str, sub: str, topic: str) -> InlineKeyboardMarkup:
    items = [(x.replace("_", " "), f"TE|{subject}|{sub}|{topic}|{x}") for x in list_tests(subject, sub, topic)]
    extra = [("◀️ Back", BACK), ("➕ Add New Test (Upload CSV)", NEW_TEST)]
    return kb_rows(items, extra)

async def addaicsv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.effective_message.reply_text("🔒 Admins only.")
    context.user_data.clear()
    await update.effective_message.reply_text("📁 Select Subject:", reply_markup=subject_keyboard())
    return A_SUBJECT

async def addaicsv_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    subj = context.user_data.get("subject")
    subsub = context.user_data.get("subsubject")
    topic = context.user_data.get("topic")

    if data == NEW_SUBJECT:
        context.user_data["awaiting"] = "subject"
        await query.edit_message_text("✅ Enter new Subject name:")
        return A_ADD_TEXT

    if data == NEW_SUBSUB:
        context.user_data["awaiting"] = "subsubject"
        await query.edit_message_text(f"✅ Enter new Sub-Subject name for <b>{subj}</b>:", parse_mode=ParseMode.HTML)
        return A_ADD_TEXT

    if data == NEW_TOPIC:
        context.user_data["awaiting"] = "topic"
        await query.edit_message_text(f"✅ Enter new Topic name for <b>{subj}</b> → <b>{subsub}</b>:", parse_mode=ParseMode.HTML)
        return A_ADD_TEXT

    if data == NEW_TEST:
        await query.edit_message_text(f"📤 Upload CSV for: <b>{subj}</b> → <b>{subsub}</b> → <b>{topic}</b>\n(It will be saved as next TestN.csv)", parse_mode=ParseMode.HTML)
        return A_WAIT_CSV

    if data == BACK:
        if topic:
            context.user_data.pop("topic", None)
            await query.edit_message_text(f"🗂 Select Topic under <b>{subj}</b> → <b>{subsub}</b>:", parse_mode=ParseMode.HTML, reply_markup=topic_keyboard(subj, subsub))
            return A_TOPIC
        if subsub:
            context.user_data.pop("subsubject", None)
            await query.edit_message_text(f"📁 Select Sub-Subject under <b>{subj}</b>:", parse_mode=ParseMode.HTML, reply_markup=subsubject_keyboard(subj))
            return A_SUBSUB
        if subj:
            context.user_data.pop("subject", None)
        await query.edit_message_text("📁 Select Subject:", reply_markup=subject_keyboard())
        return A_SUBJECT

    if data.startswith("S|"):
        _, s = data.split("|", 1)
        context.user_data["subject"] = s
        await query.edit_message_text(f"📁 Subject: <b>{s.replace('_',' ')}</b>\nSelect Sub-Subject:", parse_mode=ParseMode.HTML, reply_markup=subsubject_keyboard(s))
        return A_SUBSUB

    if data.startswith("SS|"):
        _, s, ss = data.split("|", 2)
        context.user_data["subject"] = s
        context.user_data["subsubject"] = ss
        await query.edit_message_text(f"🗂 {s.replace('_',' ')} → <b>{ss.replace('_',' ')}</b>\nSelect Topic:", parse_mode=ParseMode.HTML, reply_markup=topic_keyboard(s, ss))
        return A_TOPIC

    if data.startswith("T|"):
        _, s, ss, t = data.split("|", 3)
        context.user_data["subject"] = s
        context.user_data["subsubject"] = ss
        context.user_data["topic"] = t
        await query.edit_message_text(f"📂 {s.replace('_',' ')} → {ss.replace('_',' ')} → <b>{t.replace('_',' ')}</b>\nSelect Test:", parse_mode=ParseMode.HTML, reply_markup=test_keyboard(s, ss, t))
        return A_TEST

    if data.startswith("TE|"):
        _, s, ss, t, test = data.split("|", 4)
        context.user_data.update({"subject": s, "subsubject": ss, "topic": t, "test": test})
        await query.edit_message_text(f"✏️ Selected: <b>{s}</b> → <b>{ss}</b> → <b>{t}</b> → <b>{test}</b>\nSend a new CSV to replace/update this test, or tap ◀️ Back.", parse_mode=ParseMode.HTML, reply_markup=kb_rows([], [("◀️ Back", BACK)]))
        return A_WAIT_CSV

    await query.edit_message_text("Unknown action. Starting over…", reply_markup=subject_keyboard())
    return A_SUBJECT

async def addaicsv_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.effective_message.reply_text(f"✅ Subject added: <b>{safe.replace('_',' ')}</b>\nSelect Sub-Subject:", parse_mode=ParseMode.HTML, reply_markup=subsubject_keyboard(safe))
        return A_SUBSUB

    if awaiting == "subsubject":
        ensure_path(subj, safe)
        context.user_data["subsubject"] = safe
        context.user_data.pop("awaiting", None)
        await update.effective_message.reply_text(f"✅ Sub-Subject added under <b>{subj.replace('_',' ')}</b>: <b>{safe.replace('_',' ')}</b>\nSelect Topic:", parse_mode=ParseMode.HTML, reply_markup=topic_keyboard(subj, safe))
        return A_TOPIC

    if awaiting == "topic":
        ensure_path(subj, subsub, safe)
        context.user_data["topic"] = safe
        context.user_data.pop("awaiting", None)
        await update.effective_message.reply_text(f"✅ Topic added: <b>{safe.replace('_',' ')}</b>\nSelect Test:", parse_mode=ParseMode.HTML, reply_markup=test_keyboard(subj, subsub, safe))
        return A_TEST

async def addaicsv_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    doc = update.effective_message.document
    if not doc or not doc.file_name.lower().endswith(".csv"):
        await update.effective_message.reply_text("✖ Please upload a .csv file.")
        return
    subj = context.user_data.get("subject")
    subsub = context.user_data.get("subsubject")
    topic = context.user_data.get("topic")
    existing_test = context.user_data.get("test")
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
        await update.effective_message.reply_text(f"✖ CSV invalid: {e}")
        return
    await update.effective_message.reply_text(f"✅ CSV saved as: <b>{subj}</b> → <b>{subsub}</b> → <b>{topic}</b> → <b>{test_name}</b>", parse_mode=ParseMode.HTML, reply_markup=test_keyboard(subj, subsub, topic))
    context.user_data.pop("test", None)
    return A_TEST

async def addaicsv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("✖ Admin flow cancelled.")
    return ConversationHandler.END

# ---------------------- USER FLOW: /aiquiz ----------------------
U_SUBJECT, U_SUBSUB, U_TOPIC, U_TEST = range(200, 204)
def u_subject_keyboard() -> InlineKeyboardMarkup:
    items = [(s.replace("_", " "), f"US|{s}") for s in list_subjects()]
    return kb_rows(items)

def u_subsubject_keyboard(s: str) -> InlineKeyboardMarkup:
    items = [(x.replace("_", " "), f"USS|{s}|{x}") for x in list_subsubjects(s)]
    extra = [("◀️ Back", BACK)]
    return kb_rows(items, extra)

def u_topic_keyboard(s: str, ss: str) -> InlineKeyboardMarkup:
    items = [(x.replace("_", " "), f"UT|{s}|{ss}|{x}") for x in list_topics(s, ss)]
    extra = [("◀️ Back", BACK)]
    return kb_rows(items, extra)

def u_test_keyboard(s: str, ss: str, t: str) -> InlineKeyboardMarkup:
    tests = list_tests(s, ss, t)
    label_items = []
    for test in tests:
        label_items.append((test.replace("_", " "), f"UTE|{s}|{ss}|{t}|{test}"))
    extra = [("◀️ Back", BACK)]
    return kb_rows(label_items, extra)

async def aiquiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not list_subjects():
        await update.effective_message.reply_text("📭 No quizzes available yet. Please try later.")
        return ConversationHandler.END
    await update.effective_message.reply_text("🧠 Choose Subject:", reply_markup=u_subject_keyboard())
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
            await query.edit_message_text(f"📂 {subj.replace('_',' ')} → {subsub.replace('_',' ')}\nChoose Topic:", reply_markup=u_topic_keyboard(subj, subsub))
            return U_TOPIC
        if subsub:
            context.user_data.pop("u_subsubject", None)
            await query.edit_message_text(f"📁 {subj.replace('_',' ')}\nChoose Sub-Subject:", reply_markup=u_subsubject_keyboard(subj))
            return U_SUBSUB
        if subj:
            context.user_data.pop("u_subject", None)
        await query.edit_message_text("🧠 Choose Subject:", reply_markup=u_subject_keyboard())
        return U_SUBJECT

    if data.startswith("US|"):
        _, s = data.split("|", 1)
        context.user_data["u_subject"] = s
        if not list_subsubjects(s):
            await query.edit_message_text("No sub-subjects available here.")
            return ConversationHandler.END
        await query.edit_message_text(f"📁 {s.replace('_',' ')}\nChoose Sub-Subject:", reply_markup=u_subsubject_keyboard(s))
        return U_SUBSUB

    if data.startswith("USS|"):
        _, s, ss = data.split("|", 2)
        context.user_data["u_subject"] = s
        context.user_data["u_subsubject"] = ss
        if not list_topics(s, ss):
            await query.edit_message_text("No topics here yet.")
            return ConversationHandler.END
        await query.edit_message_text(f"🗂 {s.replace('_',' ')} → {ss.replace('_',' ')}\nChoose Topic:", reply_markup=u_topic_keyboard(s, ss))
        return U_TOPIC

    if data.startswith("UT|"):
        _, s, ss, t = data.split("|", 3)
        context.user_data.update({"u_subject": s, "u_subsubject": ss, "u_topic": t})
        if not list_tests(s, ss, t):
            await query.edit_message_text("No tests here yet.")
            return ConversationHandler.END
        await query.edit_message_text(f"📂 {s.replace('_',' ')} → {ss.replace('_',' ')} → {t.replace('_',' ')}\nChoose Test:", reply_markup=u_test_keyboard(s, ss, t))
        return U_TEST

    if data.startswith("UTE|"):
        _, s, ss, t, test = data.split("|", 4)
        csv_path = QUIZ_ROOT / s / ss / t / f"{test}.csv"
        await query.edit_message_text(f"⏳ Starting: <b>{s.replace('_',' ')}</b> → <b>{ss.replace('_',' ')}</b> → <b>{t.replace('_',' ')}</b> → <b>{test.replace('_',' ')}</b>", parse_mode=ParseMode.HTML)
        await send_mcqs_from_csv(update, context, csv_path)
        return ConversationHandler.END

    await query.edit_message_text("Unknown option. Please run /aiquiz again.")
    return ConversationHandler.END

async def cancel_common(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("✖ Cancelled.")
    return ConversationHandler.END

# ---------------------- /start ----------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        """
👋 Welcome to AI Quiz Bot!

User:
/aiquiz — Attempt quizzes by navigating Subject → Topic → Test

Admin:
/addaicsv — Add Subjects/Sub-Subjects/Topics and upload CSVs as Tests

Tip: CSV columns → "Question, Option A, Option B, Option C, Option D, Answer, Description"
        """.strip()
    )

# ---------------------- APPLICATION ----------------------
def build_app() -> Application:
    if not BOT_TOKEN:
        raise SystemExit("Please set BOT_TOKEN env var.")
    app = Application.builder().token(BOT_TOKEN).build()

    # Admin conv
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

    # User conv
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

    app.add_handler(CallbackQueryHandler(show_answers_callback, pattern=r"^show_answers\|\d+$"))
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(admin_conv)
    app.add_handler(user_conv)

    # PollAnswer handler (must be added)
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    return app

if __name__ == "__main__":
    application = build_app()
    application.run_polling(close_loop=False)
