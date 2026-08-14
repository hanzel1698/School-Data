"""Classify a Kerala school staff post designation into a section bucket.

Why this module exists: Sametham lists staff by post designation inside a table
whose own heading is the *school's* category, not the section the staff belong
to. A school headed "Staff Details - HS" routinely contains LP and UP posts. So
the section has to be read off the designation itself.

Buckets
-------
LP              posts that can only be LP (classes 1-4)
UP              posts that can only be UP (classes 5-7)
LP_UP_SHARED    posts spanning LP and UP with no field on the page to split
                them - chiefly the LP/UP language teachers, who are sanctioned
                on students opting for that language and teach across 1-7
HS_PLUS         high school and above
NON_TEACHING    clerical, menial and support posts
UNCLASSIFIED    anything unmatched - deliberately surfaced, never absorbed

Rule order matters and is load-bearing: "Teacher (LP/UP) - Arabic (Grade II)"
must reach the shared rule before the LP or UP rules, and "High School
Assistant Arabic" must reach the HS rule before any Arabic-based shared rule.
Rules are evaluated top to bottom, first match wins.
"""

from __future__ import annotations

import re
from enum import Enum


class Section(str, Enum):
    LP = "LP"
    UP = "UP"
    LP_UP_SHARED = "LP_UP_SHARED"
    HS_PLUS = "HS_PLUS"
    NON_TEACHING = "NON_TEACHING"
    UNCLASSIFIED = "UNCLASSIFIED"

    @property
    def is_teaching(self) -> bool:
        return self in {
            Section.LP,
            Section.UP,
            Section.LP_UP_SHARED,
            Section.HS_PLUS,
        }


def normalise(designation: str) -> str:
    """Fold spacing/punctuation variants so one rule covers 'L P' and 'LP'."""
    text = designation.lower().replace("\xa0", " ")
    text = re.sub(r"[.\-–—]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # "l p school" -> "lp school", "u p school" -> "up school"
    text = re.sub(r"\bl\s+p\b", "lp", text)
    text = re.sub(r"\bu\s+p\b", "up", text)
    text = re.sub(r"\bh\s+s\b", "hs", text)
    text = re.sub(r"\bp\s+d\b", "pd", text)
    return text


# (compiled pattern, section, human-readable note for the audit table)
RULES: list[tuple[re.Pattern[str], Section, str]] = [
    # --- non-teaching, first so support posts never fall through to a teaching
    # rule via an incidental word match ---
    (re.compile(r"\bclerk\b|\bclerical\b|\bhead\s*clerk\b"), Section.NON_TEACHING, "clerk"),
    # "Attendant" and "Attendent" both occur.
    (re.compile(r"office\s+attend[ae]nt|\battender\b|\bpeon\b"), Section.NON_TEACHING, "office attendant"),
    # The site spells this "Menial", "Mineal" and "Meneal".
    (re.compile(r"\bm[ei]n[ei]al\b|\bftm\b|\bptm\b"), Section.NON_TEACHING, "menial"),
    (re.compile(r"\bwatch\s*man\b|\bsweeper\b|\bcook\b|\bcleaner\b|\bgardener\b|\bdriver\b|\bayah\b"), Section.NON_TEACHING, "support staff"),
    (re.compile(r"lab(oratory)?\s+assistant|\bstore\s*keeper\b|\btypist\b|\bcomputer\s+assistant\b"), Section.NON_TEACHING, "technical support"),
    (re.compile(r"\blibrarian\b|\blibrary\s+assistant\b"), Section.NON_TEACHING, "library"),

    # --- explicit LP/UP posts, ahead of the HS block: "Headmaster LP/UP" must
    # not be swallowed by the generic headmaster rule below ---
    (re.compile(r"lp\s*/\s*up|up\s*/\s*lp"), Section.LP_UP_SHARED, "explicit LP/UP post"),

    # --- high school and above, before any subject-based rule ---
    (re.compile(r"high\s*school\s+(assistant|asst)|\bhsa\b"), Section.HS_PLUS, "HSA"),
    (re.compile(r"headmaster|headmistress|head\s*master|head\s*mistress"), Section.HS_PLUS, "HS head; LP/UP head matched earlier"),
    (re.compile(r"\bprincipal\b|\bvice\s+principal\b"), Section.HS_PLUS, "principal"),
    (re.compile(r"\bhss\b|higher\s+secondary|\bvhss\b|\bvhse\b|vocational|\blecturer\b"), Section.HS_PLUS, "higher secondary / teacher education"),
    (re.compile(r"\binstructor\b"), Section.HS_PLUS, "workshop/vocational instructor"),
    (re.compile(r"\bpd\s+teacher\b|physical\s+education\s+teacher|\bpet\b"), Section.HS_PLUS, "physical education"),
    (re.compile(r"drawing\s+teacher|sewing\s+teacher|needle\s*work\s+teacher|craft\s+teacher|music\s+teacher|\bart\s+teacher\b"), Section.HS_PLUS, "specialist teacher"),

    # --- remaining LP/UP shared posts, before the LP-only and UP-only rules.
    # Everything HS-level has already been claimed above, so any surviving
    # mention of a primary-stream language post is LP/UP by elimination. The
    # site misspells Urdu as "Urudu" and varies word order ("Junior Arabic
    # Teacher" vs "Junior Teacher Urdu"), so match the language anywhere. ---
    # "pre primary" is a distinct (below-LP) stage, so it must not be swept in.
    (re.compile(r"(?<!pre )\bprimary\b"), Section.LP_UP_SHARED, "primary-stage post"),
    # A bare language name is enough here: every HS-level language post
    # ("High School Assistant Arabic") was already claimed above, so anything
    # still unmatched that names a primary-stream language is LP/UP. This also
    # catches post names with no "teacher" in them, e.g. "Lower Grade Arabic".
    (re.compile(r"\b(arabic|urdu|urudu|sanskrit|hindi)\b"), Section.LP_UP_SHARED, "primary-stream language post"),

    # --- section-specific teaching posts ---
    (re.compile(r"\bup\s+school\s+assistant\b|\bupsa\b|teacher\s*\(\s*up\s+school\s*\)"), Section.UP, "UPSA"),
    (re.compile(r"\blp\s+school\s+assistant\b|\blpsa\b|teacher\s*\(\s*lp\s+school\s*\)"), Section.LP, "LPSA"),
]


def classify(designation: str) -> tuple[Section, str]:
    """Return (section, matched-rule note) for a designation string."""
    text = normalise(designation)
    for pattern, section, note in RULES:
        if pattern.search(text):
            return section, note
    return Section.UNCLASSIFIED, "no rule matched"


def classify_section(designation: str) -> Section:
    return classify(designation)[0]
