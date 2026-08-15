#!/usr/bin/env python3
"""PDF rendering for the Malayalam RTI applications.

Malayalam is a complex script: it needs OpenType shaping for conjuncts
(ദ്യ, ണ്ണ, ക്ഷ), chillu letters (ർ, ൾ, ൻ) and pre-base vowel signs
(േ, ൈ) that render to the LEFT of the consonant they logically follow.
Most Python PDF libraries do no shaping at all and produce broken output
that still *looks* like text - so this module goes through MuPDF, which
shapes via HarfBuzz.

`fitz.Story` is used rather than `insert_htmlbox` because Story paginates
flowing content across pages on its own.
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass
from pathlib import Path

import fitz

A4_PORTRAIT = fitz.paper_rect("a4")
A4_LANDSCAPE = fitz.paper_rect("a4-l")

# Noto Serif Malayalam ships with Windows 11. There is no static "Regular"
# weight in that set - the variable font carries it - so the variable file is
# used for body text and the static Bold for emphasis.
_FONT_CANDIDATES = {
    "regular": [
        "NotoSerifMalayalam-VariableFont_wght.ttf",
        "NotoSerifMalayalam-Medium.ttf",
        "NotoSerifMalayalam-Light.ttf",
    ],
    "bold": [
        "NotoSerifMalayalam-Bold.ttf",
        "NotoSerifMalayalam-SemiBold.ttf",
    ],
}

_SYSTEM_FONT_DIR = Path("C:/Windows/Fonts")


class FontError(RuntimeError):
    pass


def ensure_fonts(font_dir: Path) -> dict[str, str]:
    """Make sure a Malayalam regular+bold pair sits in `font_dir`.

    Copies from the Windows font directory on first run so the generator has
    a self-contained font folder it can hand to MuPDF as an Archive.
    Returns {"regular": filename, "bold": filename}.
    """
    font_dir.mkdir(parents=True, exist_ok=True)
    chosen: dict[str, str] = {}

    for role, candidates in _FONT_CANDIDATES.items():
        for name in candidates:
            local = font_dir / name
            if local.exists():
                chosen[role] = name
                break
            system = _SYSTEM_FONT_DIR / name
            if system.exists():
                shutil.copy2(system, local)
                chosen[role] = name
                break
        if role not in chosen:
            raise FontError(
                f"No Malayalam {role} font found. Looked for "
                f"{', '.join(candidates)} in {font_dir} and {_SYSTEM_FONT_DIR}.\n"
                "Install Noto Serif Malayalam (https://fonts.google.com/noto/specimen/Noto+Serif+Malayalam) "
                f"or drop the .ttf files into {font_dir}."
            )
    return chosen


def build_css(fonts: dict[str, str], body_pt: float = 10.4) -> str:
    """CSS for MuPDF's HTML engine. Keep it conservative - it is a subset."""
    return f"""
@font-face {{ font-family: mal; src: url({fonts['regular']}); }}
@font-face {{ font-family: mal; font-weight: bold; src: url({fonts['bold']}); }}

* {{ font-family: mal; }}
body {{ font-size: {body_pt}pt; line-height: 1.75; }}

p {{ margin: 0 0 9pt 0; text-align: justify; }}
p.tight {{ margin: 0 0 3pt 0; }}
p.addr {{ margin: 0; line-height: 1.55; }}
p.subject {{ margin: 12pt 0 10pt 0; font-weight: bold; }}
/* Left-aligned, not justified: these are short indented blocks and
   justification opens distracting rivers of white space in Malayalam. */
p.note {{ margin: 4pt 0 9pt 20pt; font-style: italic; text-align: left; }}
p.sub {{ margin: 0 0 5pt 22pt; text-align: left; }}

div.item {{ margin: 0 0 9pt 0; }}
div.sign {{ margin-top: 16pt; line-height: 1.85; }}
div.encl {{ margin-top: 12pt; }}

h1.doctitle {{ font-size: {body_pt + 1.5}pt; margin: 0 0 14pt 0; text-align: center; }}
h2.annex {{ font-size: {body_pt + 1}pt; margin: 0 0 8pt 0; }}

table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 0.5pt solid #666; padding: 2.5pt 3pt; font-size: {body_pt - 2.2}pt;
          line-height: 1.35; vertical-align: top; }}
/* Headers sit a size smaller than the cells: the Malayalam column labels are
   long single words that otherwise overflow into the neighbouring cell. */
th {{ font-weight: bold; background-color: #e8e8e8; text-align: center;
      font-size: {body_pt - 3.5}pt; line-height: 1.25; }}
td.num {{ text-align: right; }}
td.fill {{ background-color: #f6f6f6; }}
"""


@dataclass
class Section:
    """One run of flowing content at one page size."""

    html: str
    mediabox: fitz.Rect
    margin_lr: float = 56.0
    margin_top: float = 52.0
    margin_bottom: float = 58.0

    @property
    def frame(self) -> fitz.Rect:
        return fitz.Rect(
            self.margin_lr,
            self.margin_top,
            self.mediabox.width - self.margin_lr,
            self.mediabox.height - self.margin_bottom,
        )


def write_pdf(
    path: Path,
    sections: list[Section],
    css: str,
    font_dir: Path,
    footer_ml: str = "",
) -> int:
    """Render `sections` into one PDF. Returns the page count.

    The whole document is built in memory and written to disk once, at the
    end. MuPDF keeps a handle on any file it writes through DocumentWriter,
    which on Windows makes a later save-back over the same path fail, so the
    destination is only ever touched by a plain write_bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = fitz.Archive(str(font_dir))

    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    for section in sections:
        story = fitz.Story(html=section.html, user_css=css, archive=archive)
        more = 1
        while more:
            device = writer.begin_page(section.mediabox)
            more, _ = story.place(section.frame)
            story.draw(device)
            writer.end_page()
    writer.close()

    data, pages = _stamp_footers(buffer.getvalue(), css, font_dir, footer_ml)
    path.write_bytes(data)
    return pages


def _stamp_footers(data: bytes, css: str, font_dir: Path, footer_ml: str) -> tuple[bytes, int]:
    """Add 'page n / N' footers after the fact.

    Story has no page-number facility, so the finished document is reopened
    and each page stamped. insert_htmlbox is used rather than insert_text
    because the footer contains Malayalam, which insert_text would not shape.
    """
    doc = fitz.open("pdf", data)
    total = doc.page_count
    archive = fitz.Archive(str(font_dir))
    for index, page in enumerate(doc, start=1):
        label = f"പേജ് {index} / {total}"
        if footer_ml:
            # Plain spaces as the separator: a middle dot is not in the
            # Malayalam font and drops out as a tofu box.
            label = f"{footer_ml} &#160;&#160;&#160;&#160; {label}"
        rect = fitz.Rect(56, page.rect.height - 44, page.rect.width - 56, page.rect.height - 18)
        page.insert_htmlbox(
            rect,
            f'<p style="text-align:right; font-size:7.6pt; color:#555; margin:0">{label}</p>',
            css=css,
            archive=archive,
        )
    out = doc.tobytes(deflate=True, garbage=3)
    doc.close()
    return out, total
