import os, csv
from config import QUIZ_ROOT, MAX_MCQS
from telegram import Poll

def list_subjects():
    return os.listdir(QUIZ_ROOT) if os.path.exists(QUIZ_ROOT) else []

def list_subsubjects(subject):
    path = f"{QUIZ_ROOT}/{subject}"
    return os.listdir(path) if os.path.exists(path) else []

def list_topics(subject, subsub):
    path = f"{QUIZ_ROOT}/{subject}/{subsub}"
    return os.listdir(path) if os.path.exists(path) else []

def list_tests(subject, subsub, topic):
    path = f"{QUIZ_ROOT}/{subject}/{subsub}/{topic}"
    return [f[:-4] for f in os.listdir(path) if f.endswith(".csv")]

async def send_csv_as_quiz(chat_id, subject, subsub, topic, test, context):
    path = f"{QUIZ_ROOT}/{subject}/{subsub}/{topic}/{test}.csv"
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= MAX_MCQS: break
            options = [row["Option A"], row["Option B"], row["Option C"], row["Option D"]]
            correct = ord(row["Answer"].strip().upper()) - 65
            await context.bot.send_poll(
                chat_id,
                question=row["Question"],
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct,
                explanation=row.get("Description", "")
  )
