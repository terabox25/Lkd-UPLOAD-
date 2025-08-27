from dataclasses import dataclass
from typing import List
import csv

@dataclass
class MCQ:
    question: str
    options: List[str]
    correct_index: int
    description: str

def parse_csv(path):
    mcqs = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                question = row["Question"].strip()
                options = [row["Option A"], row["Option B"], row["Option C"], row["Option D"]]
                answer = row["Answer"].strip().upper()
                description = row.get("Description", "").strip()
                correct_index = "ABCD".index(answer)
                mcqs.append(MCQ(question, options, correct_index, description))
            except Exception as e:
                print("Skipping row:", e)
                continue
    return mcqs
