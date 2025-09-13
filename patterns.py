import re

# Har pattern ek regex aur ek parser function ke saath
PATTERNS = [
    {
        "name": "basic_mcq",
        "regex": re.compile(
            r"(?P<qnum>\d+\. .*?)\n"
            r"\(?a\)?\.?\s*(?P<a>.*?)\n"
            r"\(?b\)?\.?\s*(?P<b>.*?)\n"
            r"\(?c\)?\.?\s*(?P<c>.*?)\n"
            r"\(?d\)?\.?\s*(?P<d>.*?)\n"
            r"(?:Answer[:.\s]*(?P<ans>.*))?",
            re.DOTALL | re.IGNORECASE
        )
    },
    {
        "name": "inline_mcq",
        "regex": re.compile(
            r"(?P<qnum>\d+\..*?)"
            r"\(a\)\s*(?P<a>.*?)\s+"
            r"\(b\)\s*(?P<b>.*?)\s+"
            r"\(c\)\s*(?P<c>.*?)\s+"
            r"\(d\)\s*(?P<d>.*?)"
            r"(?:Answer[:.\s]*(?P<ans>.*))?",
            re.DOTALL | re.IGNORECASE
        )
    },
    {
        "name": "with_description",
        "regex": re.compile(
            r"(?P<qnum>\d+\..*?)\n"
            r"\(a\)\s*(?P<a>.*?)\n"
            r"\(b\)\s*(?P<b>.*?)\n"
            r"\(c\)\s*(?P<c>.*?)\n"
            r"\(d\)\s*(?P<d>.*?)\n"
            r"Solution[:.\s]*(?P<desc>.*?)\n"
            r"Answer[:.\s]*(?P<ans>.*)",
            re.DOTALL | re.IGNORECASE
        )
    }
]
