"""Strip direct identifiers from resume text before it reaches an LLM (PLAN.md §11.8).

Removes emails, URLs (incl. bare linkedin.com/... and github.com/...), phone numbers and a
best-effort candidate name. PURE: no I/O.

Name (rules from the stress test, eval/stress/REPORT.md, ADR-0007):
- Only the FIRST meaningful line is a candidate (after "Resume" / "CV" headings and a
  "Name:" label). If it is not name-like, no name is redacted: guessing further down
  erased job titles ("Registered Nurse") instead.
- Unicode letters and lowercase particles count ("José Hernández", "Ana de la Cruz").
- Only the FULL name is replaced (whole words). A lone first name is left alone: names
  like Ruby, Sydney or Austin are also skills and places the scorer needs, and a first
  name on its own is not a direct identifier once email, phone, URL and full name are gone.

Deliberately conservative on phones: digit runs must look like phone numbers (7-15 digits,
phone punctuation) so year ranges ("2018 - 2021", "2019.01 - 2021.12"), metrics
("2k requests/second", "1 200 000 users") and versions ("Python 3.12") survive.
"""

import re
from dataclasses import dataclass, field

# Placeholder tokens (not secrets).
EMAIL_TOKEN = "[EMAIL]"  # noqa: S105
PHONE_TOKEN = "[PHONE]"  # noqa: S105
URL_TOKEN = "[URL]"  # noqa: S105
NAME_TOKEN = "[CANDIDATE]"  # noqa: S105

# "+44 7700..." / "+1 (415)..." / "+91-98...": the country dialing code before the first
# separator. Kept in the placeholder ("[PHONE +44]") because it is often the resume's
# only location signal; the number itself is removed. No separator => code is ambiguous.
_COUNTRY_CODE = re.compile(r"^\+(\d{1,3})[\s(.-]")

# \w is Unicode-aware: "müller@..." is removed whole, not left as "mü[EMAIL]".
_EMAIL = re.compile(r"[\w.%+'-]+@[\w-]+(?:\.[\w-]+)*\.[^\W\d_]{2,}")
_URL = re.compile(
    r"""(?ix)
    \b(?:https?://|www\.)\S+
    | \b(?:[a-z0-9-]+\.)*(?:linkedin|github|gitlab|bitbucket|twitter|x|medium|behance|dribbble)
      \.com/\S*
    """
)
# Phone candidates: optional +, then digits with spaces / dots / dashes / parentheses.
_PHONE_CANDIDATE = re.compile(r"(?<![\w.])\+?\(?\d[\d\s().-]{5,}\d(?![\w.])")
# A date: 2019, 2019.01, 2019/01, 01.2019, 01/2019. Ranges of these are not phones.
_DATE_PART = re.compile(r"^\(?(?:(?:19|20)\d{2}(?:[./]\d{1,2})?|\d{1,2}[./](?:19|20)\d{2})\)?$")
_DATE_RANGE_SEP = re.compile(r"\s*[-\u2013]\s*")
# Digits grouped by spaces in thousands/lakhs ("1 200 000", "12 00 000"): an amount, not
# a phone. Phones end in a 4+ digit group or start with "+" / "(".
_GROUPED_AMOUNT = re.compile(r"^\d{1,3}(?: \d{2,3})+$")
_AMOUNT_LAST_GROUP = 3
# One word of a name: a capitalised Unicode word ("José", "O'Neil", "Mary-Jane"), an
# initial ("J." or "Ó"), or a lowercase particle.
_NAME_WORD = re.compile(r"^[^\W\d_][^\W\d_'\u2019-]*\.?$")
_PARTICLES = frozenset(
    [
        "de",
        "la",
        "del",
        "della",
        "da",
        "das",
        "do",
        "dos",
        "di",
        "du",
        "van",
        "von",
        "der",
        "den",
        "ten",
        "ter",
        "le",
        "bin",
        "binti",
        "al",
        "el",
        "y",
        "e",
    ]
)
_NAME_LABEL = re.compile(r"^(?:candidate\s+)?name\s*:\s*", re.IGNORECASE)
# Headings that may sit above the name; skipped when looking for the first real line.
_HEADINGS = frozenset(["resume", "résumé", "cv", "curriculum vitae", "biodata"])
# Text after one of these on the name line is a title or contact detail, not the name.
_NAME_LINE_SPLIT = re.compile(r"\s*(?:[|,\u00b7\u2022]|\s[-\u2013\u2014]\s)\s*")
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
    parts = _DATE_RANGE_SEP.split(stripped)
    if len(parts) > 1 and all(_DATE_PART.match(p) for p in parts):
        return False  # "2018 - 2021", "2019.01 - 2021.12"
    # "1 200 000", "12 00 000" are amounts.
    is_amount = bool(_GROUPED_AMOUNT.match(stripped)) and (
        len(stripped.rsplit(" ", 1)[1]) == _AMOUNT_LAST_GROUP
    )
    return not is_amount


def _is_name_word(word: str) -> bool:
    if word in _PARTICLES:
        return True
    return bool(_NAME_WORD.match(word)) and word[0].isupper()


def _find_name(text: str) -> str | None:
    """The name is the first meaningful line, or nothing (never a guess further down)."""
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line.lower().strip(" :") in _HEADINGS:
            continue
        line = _NAME_LABEL.sub("", line)
        line = _NAME_LINE_SPLIT.split(line, maxsplit=1)[0].strip()
        words = line.split()
        capitalised = [w for w in words if w not in _PARTICLES]
        if (
            2 <= len(words) <= 5
            and len(capitalised) >= 2
            and all(_is_name_word(w) for w in words)
            and not any(w.lower().strip(".") in _NOT_NAME_WORDS for w in words)
        ):
            return line
        return None
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
            code = _COUNTRY_CODE.match(match.group(0).strip())
            return f"[PHONE +{code.group(1)}]" if code else PHONE_TOKEN
        return match.group(0)

    text = _PHONE_CANDIDATE.sub(phone, text)

    name = _find_name(text)
    if name:
        # Full name only, whole words, any case ("PRIYA SHARMA" in a header, "Priya Sharma"
        # in a signature). See the module docstring for why a lone first name is kept.
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in name.split()) + r"(?!\w)"
        text, n = re.subn(pattern, NAME_TOKEN, text, flags=re.IGNORECASE)
        counts["name"] += n

    return Redaction(text=text, counts=counts)
