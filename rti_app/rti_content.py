#!/usr/bin/env python3
"""Office registry and Malayalam application text.

Everything a person might want to reword lives here rather than in the
renderer. The drafts mirror output/rti_toolkit_malayalam.md - if you change
the wording in one, change it in the other.

Scope is fixed to class-teacher posts: LP School Assistant and UP School
Assistant at all grades. Language-teacher posts (Arabic, Sanskrit, Urdu,
Hindi) and Headmaster LP/UP posts are explicitly excluded, and each draft
says so, so that a PIO cannot pad the reply with the full fixation order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

MONTHS_ML = [
    "ജനുവരി", "ഫെബ്രുവരി", "മാർച്ച്", "ഏപ്രിൽ", "മേയ്", "ജൂൺ",
    "ജൂലൈ", "ഓഗസ്റ്റ്", "സെപ്റ്റംബർ", "ഒക്ടോബർ", "നവംബർ", "ഡിസംബർ",
]


def format_date_ml(d: date) -> str:
    """2026-08-15 -> '2026 ഓഗസ്റ്റ് 15'."""
    return f"{d.year} {MONTHS_ML[d.month - 1]} {d.day}"


# --------------------------------------------------------------------------
# Offices
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Office:
    """One addressee.

    `sub_district` and `edu_district` carry the ENGLISH spellings used in
    data/processed/malappuram_staff.csv, because they are what the annexure
    is filtered on. `*_ml` fields are what gets printed.
    """

    key: str                      # filename-safe id
    kind: str                     # "DDE" | "AEO" | "KPSC"
    designation_ml: str           # office designation, printed under the SPIO line
    place_ml: str                 # place, printed after the designation
    edu_district: str | None = None   # English; None for DDE (whole district) and KPSC
    sub_district: str | None = None   # English; set for AEO only


DDE = Office(
    key="A_DDE_Malappuram",
    kind="DDE",
    designation_ml="വിദ്യാഭ്യാസ ഉപഡയറക്ടറുടെ കാര്യാലയം",
    place_ml="മലപ്പുറം, കേരളം",
)

KPSC = Office(
    key="C_KPSC",
    kind="KPSC",
    designation_ml="കേരള പബ്ലിക് സർവീസ് കമ്മീഷൻ",
    place_ml="തിരുവനന്തപുരം, കേരളം",
)

# 17 AEO sub-districts, grouped by the 4 educational districts.
# English spellings match malappuram_staff.csv exactly - do not "tidy" them.
AEOS: tuple[Office, ...] = tuple(
    Office(
        key=f"B_AEO_{sub_en}",
        kind="AEO",
        designation_ml="ഉപജില്ലാ വിദ്യാഭ്യാസ ഓഫീസറുടെ കാര്യാലയം",
        place_ml=f"{sub_ml}, മലപ്പുറം ജില്ല, കേരളം",
        edu_district=edu_en,
        sub_district=sub_en,
    )
    for edu_en, sub_en, sub_ml in [
        ("Malappuram", "Kizhisseri", "കിഴിശ്ശേരി"),
        ("Malappuram", "Kondotty", "കൊണ്ടോട്ടി"),
        ("Malappuram", "Malappuram", "മലപ്പുറം"),
        ("Malappuram", "Manjeri", "മഞ്ചേരി"),
        ("Malappuram", "Mankada", "മങ്കട"),
        ("Malappuram", "Perinthalmanna", "പെരിന്തൽമണ്ണ"),
        ("Thirurangadi", "Parappanangadi", "പരപ്പനങ്ങാടി"),
        ("Thirurangadi", "Tanur", "താനൂർ"),
        ("Thirurangadi", "Vengara", "വേങ്ങര"),
        ("Tirur", "Edappal", "എടപ്പാൾ"),
        ("Tirur", "Kuttippuram", "കുറ്റിപ്പുറം"),
        ("Tirur", "Ponnani", "പൊന്നാനി"),
        ("Tirur", "Tirur", "തിരൂർ"),
        ("Wandoor", "Areacode", "അരീക്കോട്"),
        ("Wandoor", "Melattur", "മേലാറ്റൂർ"),
        ("Wandoor", "Nilambur", "നിലമ്പൂർ"),
        ("Wandoor", "Wandoor", "വണ്ടൂർ"),
    ]
)

AEO_BY_NAME = {o.sub_district: o for o in AEOS}


# --------------------------------------------------------------------------
# Shared paragraphs
# --------------------------------------------------------------------------

SUBJECT_RTI = "വിഷയം: വിവരാവകാശ നിയമം, 2005 പ്രകാരമുള്ള അപേക്ഷ"
SUBJECT_APPEAL = "വിഷയം: വിവരാവകാശ നിയമം, 2005 വകുപ്പ് 19(1) പ്രകാരമുള്ള ഒന്നാം അപ്പീൽ"

# The scope exclusion. Printed as an indented note under item 1 of every
# application, and it is the load-bearing sentence of the whole request.
EXCLUSION_NOTE = (
    "ഭാഷാധ്യാപക തസ്തികകൾ (അറബിക്, സംസ്കൃതം, ഉർദു, ഹിന്ദി), എൽ.പി./യു.പി. "
    "പ്രധാനാധ്യാപക തസ്തികകൾ എന്നിവ സംബന്ധിച്ച വിവരം ഞാൻ ആവശ്യപ്പെടുന്നില്ല; "
    "അവ മറുപടിയിൽ നിന്ന് ഒഴിവാക്കാവുന്നതാണ്."
)

FORM_OF_INFO = (
    "<b>വിവരം ആവശ്യപ്പെടുന്ന രൂപം:</b> മേൽപ്പറഞ്ഞ വിവരങ്ങൾ <b>സമ്പൂർണ്ണ (Sampoorna)</b> "
    "സംവിധാനത്തിൽ ഇലക്ട്രോണിക് രൂപത്തിൽ സൂക്ഷിച്ചിട്ടുള്ളതിനാൽ, നിയമത്തിലെ "
    "<b>വകുപ്പ് 2(j)(ii)-ഉം വകുപ്പ് 7(9)-ഉം</b> പ്രകാരം താഴെ നൽകിയിരിക്കുന്ന ഇ-മെയിൽ "
    "വിലാസത്തിലേക്ക് <b>സ്പ്രെഡ്ഷീറ്റ് (CSV/Excel)</b> ആയി ലഭ്യമാക്കണമെന്ന് അപേക്ഷിക്കുന്നു. "
    "ഏതെങ്കിലും ഭാഗം ഇലക്ട്രോണിക് രൂപത്തിൽ ലഭ്യമല്ലെങ്കിൽ, ആ ഭാഗത്തിന്റെ മാത്രം "
    "സാക്ഷ്യപ്പെടുത്തിയ പകർപ്പ് നൽകിയാൽ മതിയാകും."
)

FEE_NORMAL = (
    "<b>ഫീസ്:</b> നിശ്ചിത അപേക്ഷാ ഫീസ് <b>10 രൂപ</b> ഇതോടൊപ്പം ചേർത്തിട്ടുണ്ട്. "
    "<b>വകുപ്പ് 7(3)</b> പ്രകാരം കൂടുതൽ ഫീസ് അടയ്ക്കേണ്ടതുണ്ടെങ്കിൽ, അതിന്റെ കണക്ക് "
    "സഹിതം നടപടി സ്വീകരിക്കുന്നതിന് മുൻപ് അറിയിക്കണമെന്ന് അഭ്യർത്ഥിക്കുന്നു."
)

FEE_BPL = (
    "<b>ഫീസ്:</b> ഞാൻ ദാരിദ്ര്യരേഖയ്ക്ക് താഴെയുള്ള (BPL) വിഭാഗത്തിൽപ്പെട്ട ആളായതിനാൽ, "
    "വിവരാവകാശ നിയമപ്രകാരം അപേക്ഷാ ഫീസിൽ നിന്ന് ഒഴിവാക്കപ്പെട്ടിട്ടുണ്ട്. "
    "ബി.പി.എൽ. കാർഡിന്റെ പകർപ്പ് ഇതോടൊപ്പം ചേർത്തിട്ടുണ്ട്."
)

TRANSFER_63 = (
    "ഈ അപേക്ഷയിലെ ഏതെങ്കിലും ഭാഗം <b>മറ്റൊരു പൊതു അധികാര സ്ഥാപനവുമായി</b> "
    "ബന്ധപ്പെട്ടതാണെങ്കിൽ, <b>വകുപ്പ് 6(3)</b> പ്രകാരം അഞ്ച് ദിവസത്തിനകം ആ ഭാഗം "
    "കൈമാറി എനിക്ക് അറിയിപ്പ് നൽകണമെന്ന് അഭ്യർത്ഥിക്കുന്നു."
)


def _item1(academic_years: list[str]) -> str:
    """Item 1 - the staff fixation order. The document that is actually wanted."""
    years = academic_years + ["", ""]
    first, second = years[0], years[1]
    second_clause = (
        f"; <b>{second}</b> വർഷത്തേത് ഇതിനകം പുറപ്പെടുവിച്ചിട്ടുണ്ടെങ്കിൽ അതിന്റെ പകർപ്പും"
        if second
        else ""
    )
    return (
        f"<b>{first}</b> അധ്യയന വർഷത്തെ <b>തസ്തിക നിർണ്ണയ ഉത്തരവിന്റെ/പ്രസ്താവനയുടെ "
        f"(staff fixation order/statement)</b> പകർപ്പ്{second_clause}. ഓരോ സ്കൂളിലും "
        "<b>അനുവദിക്കപ്പെട്ട എൽ.പി. സ്കൂൾ അസിസ്റ്റന്റ് (LPSA / LPST), യു.പി. സ്കൂൾ "
        "അസിസ്റ്റന്റ് (UPSA / UPST)</b> തസ്തികകളുടെ എണ്ണം — പ്രസ്തുത തസ്തികകളുടെ "
        "<b>എല്ലാ ഗ്രേഡുകളും</b> (ഗ്രേഡ് II, ഗ്രേഡ് I, സീനിയർ ഗ്രേഡ്, ഹയർ ഗ്രേഡ്) "
        "വെവ്വേറെ കാണിക്കുന്ന വിധത്തിൽ."
    )


ITEM2 = (
    "ഈ അപേക്ഷയുടെ തീയതിയിലെ നിലയിൽ, മേൽപ്പറഞ്ഞ ഓരോ അനുവദിക്കപ്പെട്ട തസ്തികയും "
    "സംബന്ധിച്ച്, <b>സ്കൂൾ തിരിച്ചും താഴെപ്പറയുന്ന ഓരോന്നും വെവ്വേറെയും</b> "
    "കാണിക്കുന്ന രേഖയുടെ പകർപ്പ്:"
)

ITEM2_SUB = [
    "<b>സ്ഥിരം/റെഗുലർ നിയമനത്തിലൂടെ</b> നികത്തപ്പെട്ട തസ്തികകളുടെ എണ്ണം;",
    "<b>ആരും ഇല്ലാതെ പൂർണ്ണമായും ഒഴിഞ്ഞുകിടക്കുന്ന</b> തസ്തികകളുടെ എണ്ണം;",
    "<b>ഒഴിവുള്ളതും എന്നാൽ നിലവിൽ ദിവസവേതന, താൽക്കാലിക അല്ലെങ്കിൽ അവധി ഒഴിവ് "
    "(leave vacancy) നിയമനത്തിലൂടെ പ്രവർത്തിപ്പിക്കുന്നതുമായ</b> തസ്തികകളുടെ എണ്ണം.",
]


def _item3(period_from: str, is_dde: bool) -> str:
    who = (
        "ഈ കാര്യാലയമോ ഇതിന്റെ കീഴിലുള്ള ജില്ലാ വിദ്യാഭ്യാസ ഓഫീസർമാരോ ഉപജില്ലാ "
        "വിദ്യാഭ്യാസ ഓഫീസർമാരോ"
        if is_dde
        else "ഈ കാര്യാലയം"
    )
    return (
        f"<b>{period_from} മുതൽ</b> ഈ അപേക്ഷയുടെ തീയതി വരെയുള്ള കാലയളവിൽ, {who} "
        "<b>കേരള പബ്ലിക് സർവീസ് കമ്മീഷന്</b> അയച്ച, പ്രസ്തുത തസ്തികകളിലെ "
        "<b>ഒഴിവ് സംബന്ധിച്ച പ്രസ്താവനയുടെ (vacancy position statement)</b> പകർപ്പ്."
    )


def _item4(period_from: str) -> str:
    # Period is already established by item 3; repeating the date here reads
    # as a contradiction rather than a restatement.
    return (
        "<b>അതേ കാലയളവിൽ</b> ഈ ജില്ലയിലെ ഗവൺമെന്റ് സ്കൂളുകളിലെ എൽ.പി./യു.പി. "
        "തസ്തികകളിൽ വിന്യസിക്കപ്പെട്ട <b>സംരക്ഷിത അധ്യാപകരുടെ (protected teachers)</b> "
        "എണ്ണം കാണിക്കുന്ന രേഖയുടെ പകർപ്പ്."
    )


ITEM5 = (
    "ഒന്നാം ഇനത്തിൽ പറഞ്ഞ തസ്തിക നിർണ്ണയം ഏത് <b>സർക്കാർ ഉത്തരവ്/ചട്ടം</b> പ്രകാരമാണ് "
    "നടത്തിയത് എന്ന് വ്യക്തമാക്കുന്ന അതിന്റെ പകർപ്പ് — അതിൽ പ്രയോഗിച്ച "
    "<b>അധ്യാപക-വിദ്യാർത്ഥി അനുപാതവും ഡിവിഷൻ രൂപീകരണ മാനദണ്ഡങ്ങളും</b> ഉൾപ്പെടെ."
)

KPSC_ITEMS = [
    "നിയമന അധികാരി കമ്മീഷന് <b>റിപ്പോർട്ട് ചെയ്ത ഒഴിവുകളുടെ എണ്ണം</b>, വർഷം തിരിച്ച് "
    "കാണിക്കുന്ന രേഖയുടെ പകർപ്പ്.",
    "പ്രസ്തുത ഒഴിവുകളിലേക്ക് <b>അഡ്വൈസ് ചെയ്ത ഉദ്യോഗാർത്ഥികളുടെ എണ്ണം</b>, വർഷം "
    "തിരിച്ച് കാണിക്കുന്ന രേഖയുടെ പകർപ്പ്.",
    "ഈ ജില്ലയിൽ പ്രസ്തുത തസ്തികകളിലേക്കുള്ള <b>റാങ്ക് ലിസ്റ്റ്(കളു)ടെ നിലവിലെ സ്ഥിതി</b> "
    "— പ്രസിദ്ധീകരിച്ച തീയതി, കാലാവധി അവസാനിക്കുന്ന തീയതി, ലിസ്റ്റിലുള്ള ആകെ "
    "ഉദ്യോഗാർത്ഥികളുടെ എണ്ണം, ഇതുവരെ അഡ്വൈസ് ചെയ്തവരുടെ എണ്ണം.",
    "റാങ്ക് ലിസ്റ്റിന്റെ കാലാവധി അവസാനിച്ചപ്പോൾ <b>നികത്തപ്പെടാതെ റദ്ദായിപ്പോയ "
    "ഒഴിവുകൾ</b> ഉണ്ടെങ്കിൽ അവയുടെ എണ്ണം, വർഷം തിരിച്ച്.",
]
