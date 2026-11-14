"""Strip direct identifiers from resume text before it reaches an LLM (PLAN.md §11.8).

Removes emails, URLs (incl. bare linkedin.com/... and github.com/...), phone numbers and a
best-effort candidate name (a 2-4 word name-like line at the top of the resume, plus any
later occurrence of it). PURE: no I/O.

Deliberately conservative on phones: digit runs must look like phone numbers (7-15 digits,
phone punctuation) so year ranges ("2018 - 2021"), metrics ("2k requests/second") and
versions ("Python 3.12") survive.
"""

import re
from dataclasses import dataclass, field

# Placeholder tokens (not secrets).
EMAIL_TOKEN = "[EMAIL]"  # noqa: S105
PHONE_TOKEN = "[PHONE]"  # noqa: S105
URL_TOKEN = "[URL]"  # noqa: S105
NAME_TOKEN = "[CANDIDATE]"  # noqa: S105

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(
    r"""(?ix)
    \b(?:https?://|www\.)\S+
    | \b(?:[a-z0-9-]+\.)*(?:linkedin|github|gitlab|bitbucket|twitter|x|medium|behance|dribbble)
      \.com/\S*
    """
)
# Phone candidates: optional +, then digits with spaces / dots / dashes / parentheses.
_PHONE_CANDIDATE = re.compile(r"(?<![\w.])\+?\(?\d[\d\s().-]{5,}\d(?![\w.])")
_YEAR_RANGE = re.compile(r"^\(?(19|20)\d{2}\)?\s*[-\u2013]\s*\(?(19|20)\d{2}\)?$")
_NAME_WORD = re.compile(r"^[A-Z][a-zA-Z'\u2019-]+$|^[A-Z]\.$")
_NAME_SCAN_LINES = 5
# A top line containing any of these is a title/heading, not a person's name.
_NOT_NAME_WORDS = frozenset(
    [
        "resume",
        "curriculum",
        "vitae",
        "cv",
        "profile",
        "summary",
        "contact",
        "experience",
        "education",
        "skills",
        "objective",
        "about",
        "senior",
        "junior",
        "lead",
        "principal",
        "staff",
        "chief",
        "head",
        "software",
        "senior",
        "engineer",
        "engineering",
        "developer",
        "manager",
        "director",
        "analyst",
        "scientist",
        "designer",
        "architect",
        "consultant",
        "specialist",
        "administrator",
        "officer",
        "intern",
        "associate",
        "assistant",
        "coordinator",
        "data",
        "backend",
        "frontend",
        "full",
        "stack",
        "cloud",
        "platform",
        "product",
        "project",
        "technical",
        "sales",
        "marketing",
        "account",
    ]
)


@dataclass
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)


def _is_phone(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    if not 7 <= len(digits) <= 15:
        return False
    stripped = candidate.strip()
    return not _YEAR_RANGE.match(stripped)


def _find_name(text: str) -> str | None:
    for line in text.split("\n")[:_NAME_SCAN_LINES]:
        words = line.strip().split()
        if (
            2 <= len(words) <= 4
            and all(_NAME_WORD.match(w) for w in words)
            and not any(w.lower().strip(".") in _NOT_NAME_WORDS for w in words)
        ):
            return " ".join(words)
    return None


def redact(text: str) -> Redaction:
    counts = {"email": 0, "url": 0, "phone": 0, "name": 0}

    def sub(pattern: re.Pattern[str], token: str, kind: str, value: str) -> str:
        result, n = pattern.subn(token, value)
        counts[kind] += n
        return result

    text = sub(_EMAIL, EMAIL_TOKEN, "email", text)
    text = sub(_URL, URL_TOKEN, "url", text)

    def phone(match: re.Match[str]) -> str:
        if _is_phone(match.group(0)):
            counts["phone"] += 1
            return PHONE_TOKEN
        return match.group(0)

    text = _PHONE_CANDIDATE.sub(phone, text)

    name = _find_name(text)
    if name:
        text, n = re.subn(re.escape(name), NAME_TOKEN, text)
        counts["name"] += n
        # Also catch the first name alone (e.g. "Jordan led ..."), only when capitalized word.
        first = name.split()[0]
        if len(first) > 2:
            text, n = re.subn(rf"\b{re.escape(first)}\b", NAME_TOKEN, text)
            counts["name"] += n

    return Redaction(text=text, counts=counts)
