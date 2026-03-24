from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json

app = FastAPI()

QUESTIONS = [
    {
        "id": "0",
        "question": "India ki capital kya hai?",
        "option_1": "Delhi",
        "option_2": "Mumbai",
        "option_3": "Chennai",
        "option_4": "Kolkata",
        "answer": "1",
        "positive_marks": "1",
        "negative_marks": "0.25",
        "solution_text": "Delhi is the capital of India."
    },
    {
        "id": "1",
        "question": "2 + 2 = ?",
        "option_1": "3",
        "option_2": "4",
        "option_3": "5",
        "option_4": "6",
        "answer": "2",
        "positive_marks": "1",
        "negative_marks": "0",
        "solution_text": "Correct answer is 4."
    }
]

@app.get("/quiz", response_class=HTMLResponse)
async def get_quiz():
    with open("template.html", encoding="utf-8") as f:
        html = f.read()

    html = html.replace(
        "{{QUESTIONS_DATA}}",
        json.dumps(QUESTIONS, ensure_ascii=False)
    ).replace(
        "{{QUIZ_TITLE}}",
        "Test Mini App Quiz"
    )

    return html
