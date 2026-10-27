"""Transparent text eligibility, NOT a sentiment or human-opinion classifier."""
import html
import re
from collections import Counter
from html.parser import HTMLParser


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


def clean_text(value):
    if not isinstance(value, str):
        return ""
    # A lightweight normalization for assessment, not production data cleaning.
    value = re.sub(r"<!--.*?-->", " ", value, flags=re.S)
    value = re.sub(r"```.*?```", " [code block] ", value, flags=re.S)
    parser = PlainText()
    parser.feed(value)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def screen(text, author_type=None):
    t = clean_text(text)
    words = re.findall(r"[^\W_]+", t, re.UNICODE)
    if author_type == "Bot":
        category = "automated_message"
    elif not t:
        category = "missing_or_empty"
    elif len(t) < 20 or len(words) < 4:
        category = "short_or_low_information"
    else:
        category = "eligible_for_manual_review"
    markers = {
        "first_person_marker": bool(re.search(r"\b(i|i'm|my|we|our)\b", t, re.I)),
        "problem_marker": bool(re.search(r"\b(bug|crash|broken|error|issue|slow|fail\w*)\b", t, re.I)),
        "request_marker": bool(re.search(r"\b(wish|please|feature|request|should|would like)\b", t, re.I)),
        "question_marker": "?" in t,
    }
    return {"text_length": len(t), "word_count": len(words), "screen": category, **markers}


def language_flag(text, label):
    # A triage flag only, not language detection. Absence of flags is not verification.
    t = clean_text(text).lower()
    if label == "english" and (re.search(r"[\u0400-\u04ff\u4e00-\u9fff]", t) or
        len(set(re.findall(r"\b(?:jogo|muito|melhor|recomendo|voce|você|nao|não)\b", t))) >= 2):
        return True
    return False


def counts(items):
    return dict(Counter(x["screen"] for x in items))
