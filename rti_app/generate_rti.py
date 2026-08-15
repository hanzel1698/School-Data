#!/usr/bin/env python3
"""Generate the Malayalam RTI applications as print-ready PDFs.

Fill in rti_app/applicant.yaml, then:

    python rti_app/generate_rti.py

Everything else - office names, the Malayalam body text, the per-office
annexure - is filled in automatically. Output lands in output/rti_pdfs/.

    python rti_app/generate_rti.py --only dde
    python rti_app/generate_rti.py --only aeo --aeo Manjeri Nilambur
    python rti_app/generate_rti.py --list-fields
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rti_content as C  # noqa: E402
import rti_pdf as P  # noqa: E402

# The Windows console defaults to the ANSI codepage, which cannot encode
# Malayalam - field labels and the missing-field report would raise instead
# of printing. Harmless where stdout is already UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent / "applicant.yaml"
DEFAULT_ANNEXURE = ROOT / "output" / "rti_annexure_schools.csv"
DEFAULT_OUT = ROOT / "output" / "rti_pdfs"
FONT_DIR = Path(__file__).resolve().parent / "fonts"

REQUIRED_FIELDS = [
    ("applicant.name_ml", "പേര് - name in Malayalam, as it should appear on the application"),
    ("applicant.address_ml", "വിലാസം - full postal address"),
    ("applicant.phone", "ഫോൺ"),
    ("applicant.email", "ഇ-മെയിൽ - the address the CSV reply should be sent to"),
    ("applicant.place_ml", "സ്ഥലം - place written above the date"),
]


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def dig(cfg: dict, dotted: str, default=None):
    node = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"Config not found: {path}\nCopy applicant.yaml and fill it in.")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def check_required(cfg: dict) -> list[str]:
    missing = []
    for dotted, label in REQUIRED_FIELDS:
        value = dig(cfg, dotted)
        if value is None or str(value).strip() == "":
            missing.append(f"  {dotted:26} {label}")
    return missing


def resolve_date(cfg: dict) -> date:
    raw = dig(cfg, "applicant.date")
    if not raw:
        return date.today()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw).strip())


# --------------------------------------------------------------------------
# Annexure
# --------------------------------------------------------------------------


def load_schools(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Annexure CSV not found: {path}\nRun the toolkit generation first.")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def schools_for(office: C.Office, schools: list[dict]) -> list[dict]:
    if office.kind == "AEO":
        return [r for r in schools if r["Educational Sub-District (AEO)"] == office.sub_district]
    if office.kind == "DDE":
        return schools
    return []


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------


def esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _inline(block: str) -> str:
    """Multi-line YAML value -> one comma-joined line, no trailing separator."""
    parts = [line.strip().rstrip(",") for line in str(block).strip().splitlines()]
    return esc(", ".join(p for p in parts if p))


def _lines(block: str) -> str:
    """Multi-line YAML value -> stacked <p class=addr> lines."""
    out = []
    for line in str(block).strip().splitlines():
        line = line.strip()
        if line:
            out.append(f'<p class="addr">{esc(line)}</p>')
    return "".join(out)


def addressee(office: C.Office, cfg: dict) -> str:
    override = dig(cfg, f"offices.{office.key}")
    parts = [
        '<p class="addr">സേവനത്തിൽ,</p>',
        '<p class="addr">സ്റ്റേറ്റ് പബ്ലിക് ഇൻഫർമേഷൻ ഓഫീസർ,</p>',
    ]
    if override and str(override).strip():
        # The override replaces the built-in designation+place rather than
        # adding to it, so an address block that repeats the office name does
        # not print it twice.
        parts.append(_lines(override))
    else:
        parts.append(f'<p class="addr">{esc(office.designation_ml)},</p>')
        parts.append(f'<p class="addr">{esc(office.place_ml)}</p>')
        parts.append(
            '<p class="addr" style="color:#777">'
            "&lt;ഓഫീസ് വിലാസം ഉറപ്പുവരുത്തി ചേർക്കുക&gt;</p>"
        )
    return "".join(parts)


def signature(cfg: dict, on: date) -> str:
    name_en = dig(cfg, "applicant.name_en", "")
    name = esc(dig(cfg, "applicant.name_ml", ""))
    if name_en:
        name += f" ({esc(name_en)})"
    rows = [
        "വിശ്വസ്തതയോടെ,",
        "",
        f"പേര്: {name}",
        f"വിലാസം: {_inline(dig(cfg, 'applicant.address_ml', ''))}",
        f"ഫോൺ: {esc(dig(cfg, 'applicant.phone', ''))}",
        f"ഇ-മെയിൽ: {esc(dig(cfg, 'applicant.email', ''))}",
        f"സ്ഥലം: {esc(dig(cfg, 'applicant.place_ml', ''))} &#160;&#160; തീയതി: {C.format_date_ml(on)}",
        "",
        "ഒപ്പ്: ______________________",
    ]
    return '<div class="sign">' + "".join(
        f'<p class="addr">{r}</p>' if r else '<p class="addr">&#160;</p>' for r in rows
    ) + "</div>"


def numbered(index: int, body: str) -> str:
    return f'<div class="item"><b>{index}.</b> {body}</div>'


def application_html(office: C.Office, cfg: dict, on: date, n_schools: int, with_annex: bool) -> str:
    years = dig(cfg, "request.academic_years", ["2025–26", "2026–27"]) or []
    vac_from = dig(cfg, "request.vacancy_period_from_ml", "2024 ജനുവരി 1")
    kpsc_from = dig(cfg, "request.kpsc_period_from_ml", "2022 ജനുവരി 1")
    bpl = bool(dig(cfg, "applicant.bpl", False))

    parts = [addressee(office, cfg)]

    if office.kind == "KPSC":
        parts.append(f'<p class="subject">{C.SUBJECT_RTI}</p>')
        parts.append("<p>സർ/മാഡം,</p>")
        parts.append(
            "<p><b>മലപ്പുറം ജില്ലയിലെ ഗവൺമെന്റ് സ്കൂളുകളിലെ</b> <b>എൽ.പി. സ്കൂൾ ടീച്ചർ / "
            "LPSA / LPST</b>, <b>യു.പി. സ്കൂൾ ടീച്ചർ / UPSA / UPST</b> എന്നീ തസ്തികകൾ "
            f"സംബന്ധിച്ച്, <b>{esc(kpsc_from)} മുതൽ</b> ഈ അപേക്ഷയുടെ തീയതി വരെയുള്ള "
            "കാലയളവിലേക്ക് താഴെപ്പറയുന്ന വിവരങ്ങൾ ലഭ്യമാക്കണമെന്ന് അപേക്ഷിക്കുന്നു:</p>"
        )
        for i, item in enumerate(C.KPSC_ITEMS, start=1):
            parts.append(numbered(i, item))
    else:
        is_dde = office.kind == "DDE"
        parts.append(f'<p class="subject">{C.SUBJECT_RTI}</p>')
        parts.append("<p>സർ/മാഡം,</p>")

        if is_dde:
            scope = (
                "മലപ്പുറം റവന്യൂ ജില്ലയിൽ എൽ.പി. വിഭാഗം (1 മുതൽ 4 വരെ ക്ലാസ്സുകൾ) "
                "കൂടാതെ/അല്ലെങ്കിൽ യു.പി. വിഭാഗം (5 മുതൽ 7 വരെ ക്ലാസ്സുകൾ) ഉള്ള "
                "<b>ഗവൺമെന്റ് സ്കൂളുകൾ</b> സംബന്ധിച്ച്"
            )
        else:
            scope = (
                f"<b>{esc(office.place_ml.split(',')[0])}</b> വിദ്യാഭ്യാസ ഉപജില്ലയിൽ എൽ.പി. "
                "വിഭാഗം (1 മുതൽ 4 വരെ ക്ലാസ്സുകൾ) കൂടാതെ/അല്ലെങ്കിൽ യു.പി. വിഭാഗം "
                "(5 മുതൽ 7 വരെ ക്ലാസ്സുകൾ) ഉള്ള <b>ഗവൺമെന്റ് സ്കൂളുകൾ</b> സംബന്ധിച്ച്"
            )

        annex_clause = (
            f" ബന്ധപ്പെട്ട സ്കൂളുകളുടെ എണ്ണം <b>{n_schools}</b> ആണ്; അവയുടെ പട്ടിക "
            "<b>അനുബന്ധം-I</b> ആയി ചേർത്തിട്ടുണ്ട്."
            if with_annex
            else f" ബന്ധപ്പെട്ട സ്കൂളുകളുടെ എണ്ണം <b>{n_schools}</b> ആണ്."
        )
        parts.append(
            f"<p>{scope} താഴെപ്പറയുന്ന വിവരങ്ങൾ ലഭ്യമാക്കണമെന്ന് അപേക്ഷിക്കുന്നു."
            f"{annex_clause}</p>"
        )

        parts.append(numbered(1, C._item1(list(years))))
        parts.append(f'<p class="note">{C.EXCLUSION_NOTE}</p>')

        parts.append(numbered(2, C.ITEM2))
        # Explicit list, not a string: Malayalam "സി" is two codepoints, so
        # iterating a string here would slice off a bare vowel sign.
        for label, sub in zip(["എ", "ബി", "സി"], C.ITEM2_SUB):
            parts.append(f'<p class="sub">({label}) {sub}</p>')

        parts.append(numbered(3, C._item3(esc(vac_from), is_dde)))
        index = 4
        if is_dde:
            parts.append(numbered(4, C._item4(esc(vac_from))))
            index = 5
        parts.append(numbered(index, C.ITEM5))

    parts.append(f"<p>{C.FORM_OF_INFO}</p>")
    parts.append(f"<p>{C.FEE_BPL if bpl else C.FEE_NORMAL}</p>")
    parts.append(f"<p>{C.TRANSFER_63}</p>")
    parts.append(signature(cfg, on))

    encl = ["അപേക്ഷാ ഫീസ്" if not bpl else "ബി.പി.എൽ. കാർഡിന്റെ പകർപ്പ്"]
    if with_annex and n_schools:
        encl.insert(0, f"അനുബന്ധം-I ({n_schools} സ്കൂളുകളുടെ പട്ടിക)")
    parts.append(
        f'<div class="encl"><p class="addr"><b>ഉള്ളടക്കം:</b> {"; ".join(encl)}.</p></div>'
    )

    return "".join(parts)


ANNEX_COLUMNS = [
    ("ക്രമ", "Sl No", "num", 4.0),
    ("സ്കൂൾ<br>കോഡ്", "School Code", "num", 6.5),
    ("സ്കൂളിന്റെ പേര്", "School Name", "", 23.0),
    ("ക്ലാസ്", "Classes Approved", "", 6.0),
    ("വി.<br>1-4", "Students 1-4", "num", 5.5),
    ("വി.<br>5-7", "Students 5-7", "num", 5.5),
    ("LPSA<br>നികത്തിയത്", "LP School Assistant posts filled (Sametham)", "num", 7.5),
    ("UPSA<br>നികത്തിയത്", "UP School Assistant posts filled (Sametham)", "num", 7.5),
    ("LPSA<br>അനുവദിച്ചത്", None, "fill", 8.6),
    ("UPSA<br>അനുവദിച്ചത്", None, "fill", 8.6),
    ("LPSA<br>ഒഴിവ്", None, "fill", 8.6),
    ("UPSA<br>ഒഴിവ്", None, "fill", 8.6),
]


def annexure_html(office: C.Office, rows: list[dict]) -> str:
    where = "മലപ്പുറം റവന്യൂ ജില്ല" if office.kind == "DDE" else office.place_ml.split(",")[0]
    head = "".join(
        f'<th style="width:{w}%">{label}</th>' for label, _, _, w in ANNEX_COLUMNS
    )
    body = []
    for row in rows:
        cells = []
        for _, source, css_class, _ in ANNEX_COLUMNS:
            value = "" if source is None else esc(row.get(source, ""))
            cells.append(f'<td class="{css_class}">{value}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

    return (
        f'<h2 class="annex">അനുബന്ധം-I &#160;|&#160; Annexure-I</h2>'
        f'<p class="tight">{esc(where)} — എൽ.പി./യു.പി. വിഭാഗമുള്ള ഗവൺമെന്റ് സ്കൂളുകൾ '
        f'({len(rows)} എണ്ണം). അവസാന നാല് കോളങ്ങൾ ഓഫീസർ പൂരിപ്പിക്കുന്നതിനുള്ളതാണ്.</p>'
        f'<p class="tight" style="color:#555; font-size:8pt">Government schools with an LP/UP '
        f'section. The last four columns are for the Public Information Officer to complete. '
        f'"നികത്തിയത്" columns are filled posts as published by Sametham, for reference only.</p>'
        f"<table><tr>{head}</tr>{''.join(body)}</table>"
    )


def appeal_html(cfg: dict, on: date) -> str:
    parts = [
        '<p class="addr">സേവനത്തിൽ,</p>',
        '<p class="addr">ഒന്നാം അപ്പീൽ അധികാരി,</p>',
        '<p class="addr" style="color:#777">&lt;ഓഫീസിന്റെ പേരും വിലാസവും&gt;</p>',
        f'<p class="subject">{C.SUBJECT_APPEAL}</p>',
        "<p>സർ/മാഡം,</p>",
        '<p><span style="color:#777">&lt;തീയതി&gt;</span>-ന് സമർപ്പിച്ച എന്റെ വിവരാവകാശ '
        'അപേക്ഷയ്ക്ക് (രജിസ്റ്റേഡ് തപാൽ നം. <span style="color:#777">&lt;...&gt;</span>, '
        'കൈപ്പറ്റിയ തീയതി <span style="color:#777">&lt;...&gt;</span>) നിയമം അനുശാസിക്കുന്ന '
        "30 ദിവസത്തിനകം മറുപടി ലഭിച്ചിട്ടില്ല / ലഭിച്ച മറുപടി അപൂർണ്ണമാണ്. അതിനാൽ ഈ "
        "അപ്പീൽ സമർപ്പിക്കുന്നു.</p>",
        '<p style="color:#777">&lt;മറുപടി അപൂർണ്ണമാണെങ്കിൽ, ഏതൊക്കെ ഇനങ്ങൾക്കാണ് മറുപടി '
        "ലഭിക്കാത്തത് എന്ന് ഇനം നമ്പർ സഹിതം ഇവിടെ എഴുതുക.&gt;</p>",
        "<p><b>വകുപ്പ് 7(6)</b> പ്രകാരം, നിശ്ചിത സമയപരിധിക്കുള്ളിൽ വിവരം നൽകാത്ത "
        "സാഹചര്യത്തിൽ ആവശ്യപ്പെട്ട വിവരം <b>യാതൊരു ഫീസും കൂടാതെ</b> നൽകേണ്ടതാണ്. കൂടാതെ, "
        "മതിയായ കാരണമില്ലാതെ വിവരം നിഷേധിക്കുകയോ സമയപരിധിക്കുള്ളിൽ നൽകാതിരിക്കുകയോ "
        "ചെയ്താൽ <b>വകുപ്പ് 20</b> പ്രകാരം പ്രതിദിനം 250 രൂപ വീതം പരമാവധി 25,000 രൂപ വരെ "
        "പിഴ ചുമത്താവുന്നതാണെന്ന വസ്തുത ബഹുമാനപൂർവ്വം ശ്രദ്ധയിൽപ്പെടുത്തുന്നു.</p>",
        "<p>ആയതിനാൽ ആവശ്യപ്പെട്ട വിവരങ്ങൾ പൂർണ്ണമായും ലഭ്യമാക്കാൻ ഉത്തരവാകണമെന്ന് "
        "അഭ്യർത്ഥിക്കുന്നു.</p>",
        signature(cfg, on),
        '<div class="encl"><p class="addr"><b>ഉള്ളടക്കം:</b> അപേക്ഷയുടെ പകർപ്പ്; '
        "തപാൽ രസീത്/അക്നോളജ്മെന്റ് കാർഡിന്റെ പകർപ്പ്; ലഭിച്ച മറുപടിയുടെ പകർപ്പ് "
        "(ഉണ്ടെങ്കിൽ).</p></div>",
        '<p style="margin-top:14pt; color:#555; font-size:9pt">രണ്ടാം അപ്പീൽ: ഒന്നാം '
        "അപ്പീൽ തീർപ്പാക്കി 90 ദിവസത്തിനകം — കേരള സംസ്ഥാന വിവരാവകാശ കമ്മീഷൻ, "
        "തിരുവനന്തപുരം.</p>",
    ]
    return "".join(parts)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def targets(args, cfg: dict) -> list[C.Office]:
    gen = dig(cfg, "generate", {}) or {}
    # Only these three keys select an addressee; the rest of `generate:` are
    # flags (aeo_list, include_annexure, appeal_template) and must not leak in.
    want = args.only or [k for k in ("dde", "kpsc", "aeo") if gen.get(k)]
    picked: list[C.Office] = []
    if "dde" in want:
        picked.append(C.DDE)
    if "kpsc" in want:
        picked.append(C.KPSC)
    if "aeo" in want:
        names = args.aeo or dig(cfg, "generate.aeo_list", []) or []
        if isinstance(names, str):
            names = [names]
        if not names or "all" in [str(n).lower() for n in names]:
            picked.extend(C.AEOS)
        else:
            for name in names:
                office = C.AEO_BY_NAME.get(str(name))
                if office is None:
                    sys.exit(
                        f"Unknown AEO sub-district: {name}\n"
                        f"Valid: {', '.join(sorted(C.AEO_BY_NAME))}"
                    )
                picked.append(office)
    return picked


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Malayalam RTI application PDFs.")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--annexure", type=Path, default=DEFAULT_ANNEXURE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", nargs="*", choices=["dde", "aeo", "kpsc"], default=None)
    ap.add_argument("--aeo", nargs="*", default=None, help="Sub-district names, or 'all'")
    ap.add_argument("--no-annexure", action="store_true")
    ap.add_argument("--no-appeal", action="store_true")
    ap.add_argument("--list-fields", action="store_true", help="Print the fields you must fill in")
    args = ap.parse_args()

    if args.list_fields:
        print("Fields you must enter in rti_app/applicant.yaml:\n")
        for dotted, label in REQUIRED_FIELDS:
            print(f"  {dotted:26} {label}")
        print("\nOptional (sensible defaults if left blank):")
        print("  applicant.name_en          name in English, printed in brackets")
        print("  applicant.date             ISO date; blank = today")
        print("  applicant.bpl              true if below poverty line (fee is waived)")
        print("  request.academic_years     default ['2025–26', '2026–27']")
        print("  request.vacancy_period_from_ml   default '2024 ജനുവരി 1'")
        print("  request.kpsc_period_from_ml      default '2022 ജനുവരി 1'")
        print("  offices.<KEY>              office postal address to print (confirm it first)")
        return

    cfg = load_config(args.config)
    missing = check_required(cfg)
    if missing:
        print("These required fields are still blank in", args.config, "\n", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        sys.exit(1)

    on = resolve_date(cfg)
    schools = load_schools(args.annexure)
    with_annex = not args.no_annexure and bool(dig(cfg, "generate.include_annexure", True))

    fonts = P.ensure_fonts(FONT_DIR)
    css = P.build_css(fonts)
    args.out.mkdir(parents=True, exist_ok=True)

    offices = targets(args, cfg)
    if not offices:
        print("Nothing selected. Enable something under `generate:` or pass --only.", file=sys.stderr)

    written = []
    for office in offices:
        rows = schools_for(office, schools)
        annex = with_annex and bool(rows)
        sections = [
            P.Section(
                application_html(office, cfg, on, len(rows), annex),
                P.A4_PORTRAIT,
            )
        ]
        if annex:
            sections.append(
                P.Section(annexure_html(office, rows), P.A4_LANDSCAPE, margin_lr=30, margin_top=34)
            )
        path = args.out / f"RTI_{office.key}.pdf"
        pages = P.write_pdf(path, sections, css, FONT_DIR, footer_ml="വിവരാവകാശ അപേക്ഷ")
        written.append((path, pages, len(rows)))

    if not args.no_appeal and dig(cfg, "generate.appeal_template", True):
        path = args.out / "RTI_D_FirstAppeal_template.pdf"
        pages = P.write_pdf(
            path,
            [P.Section(appeal_html(cfg, on), P.A4_PORTRAIT)],
            css,
            FONT_DIR,
            footer_ml="ഒന്നാം അപ്പീൽ",
        )
        written.append((path, pages, 0))

    print(f"\nWrote {len(written)} PDF(s) to {args.out}\n")
    for path, pages, n in written:
        detail = f"{n} schools in annexure" if n else "no annexure"
        print(f"  {path.name:44} {pages:>3} pages   {detail}")


if __name__ == "__main__":
    main()
