import fitz
import csv
from patterns import PATTERNS

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    return text

def parse_mcqs(text):
    results = []
    for pattern in PATTERNS:
        for match in pattern["regex"].finditer(text):
            q = match.group("qnum").strip() if match.group("qnum") else ""
            a = match.group("a").strip() if match.group("a") else ""
            b = match.group("b").strip() if match.group("b") else ""
            c = match.group("c").strip() if match.group("c") else ""
            d = match.group("d").strip() if match.group("d") else ""
            ans = match.group("ans").strip() if match.group("ans") else ""
            desc = match.group("desc").strip() if "desc" in match.groupdict() and match.group("desc") else ""
            
            results.append([q, a, b, c, d, ans, desc])
    return results

def write_csv(mcqs, output_path):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Question", "Option A", "Option B", "Option C", "Option D", "Answer", "Description"])
        writer.writerows(mcqs)
