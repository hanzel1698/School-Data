# RTI PDF generator

Turns the drafts in `output/rti_toolkit_malayalam.md` into print-ready
Malayalam PDFs, each with its own annexure of schools already filled in.

```bash
python rti_app/generate_rti.py
```

Output goes to `output/rti_pdfs/`.

---

## The fields you fill in

Everything lives in **`rti_app/applicant.yaml`**. That is the only file you
need to touch. Run `python rti_app/generate_rti.py --list-fields` to print
this same list.

### Required — the script refuses to run until these are set

| Field | What it is |
|---|---|
| `applicant.name_ml` | Your name in Malayalam, as it should appear on the application |
| `applicant.address_ml` | Full postal address (multi-line block) |
| `applicant.phone` | Phone number |
| `applicant.email` | Where the CSV reply should be sent — this is what item "form of information" points at, so get it right |
| `applicant.place_ml` | Place written above the date, e.g. `മലപ്പുറം` |

### Optional — sensible defaults if left blank

| Field | Default |
|---|---|
| `applicant.name_en` | blank; if set, printed in brackets after the Malayalam name |
| `applicant.date` | today's date when you run it |
| `applicant.bpl` | `false`. Set `true` and the fee paragraph switches to the BPL exemption and the enclosure list asks for a card copy instead of the ₹10 |
| `request.academic_years` | `["2025–26", "2026–27"]` |
| `request.vacancy_period_from_ml` | `2024 ജനുവരി 1` |
| `request.kpsc_period_from_ml` | `2022 ജനുവരി 1` |
| `offices.<KEY>` | a visible `<confirm the office address>` placeholder |

### Office addresses

**Confirm these before posting.** No address is hardcoded, because a wrong
one is worse than a blank one. Any office you do not fill in prints a grey
placeholder on the PDF rather than silently omitting the line, so an unfilled
address cannot slip past you.

Keys are `A_DDE_Malappuram`, `C_KPSC`, and `B_AEO_<SubDistrict>` for each of
the 17 AEOs (e.g. `B_AEO_Manjeri`).

---

## Choosing what to generate

Under `generate:` in the YAML:

```yaml
generate:
  dde: true            # one application covering the whole revenue district
  kpsc: true           # the recruitment side
  aeo: false           # per-AEO applications
  aeo_list: ["all"]    # or e.g. ["Manjeri", "Nilambur"]
  appeal_template: true
  include_annexure: true
```

Or from the command line, which overrides the file:

```bash
python rti_app/generate_rti.py --only dde
```

```bash
python rti_app/generate_rti.py --only aeo --aeo Manjeri Nilambur
```

The 17 valid AEO names: Kizhisseri, Kondotty, Malappuram, Manjeri, Mankada,
Perinthalmanna, Parappanangadi, Tanur, Vengara, Edappal, Kuttippuram,
Ponnani, Tirur, Areacode, Melattur, Nilambur, Wandoor.

---

## What comes out

| File | Pages | Annexure |
|---|---:|---|
| `RTI_A_DDE_Malappuram.pdf` | ~20 | all 519 schools |
| `RTI_B_AEO_<name>.pdf` | 3–5 | that sub-district only (19–52 schools) |
| `RTI_C_KPSC.pdf` | 2 | none — the PSC holds no school-level data |
| `RTI_D_FirstAppeal_template.pdf` | 1 | none — blanks to fill in by hand on day 31 |

The application body is A4 portrait; annexure pages switch to A4 landscape
in the same file, so the table fits without shrinking to unreadable type.
The last four annexure columns are shaded and left empty for the Public
Information Officer to complete.

---

## Notes on how it works

**Scope.** Every application asks only for LP School Assistant and UP School
Assistant posts at all grades, and explicitly says language-teacher posts
(Arabic, Sanskrit, Urdu, Hindi) and Headmaster LP/UP posts are not sought.
That sentence is load-bearing — without it a PIO can return the whole staff
fixation order and leave you to unpick it.

**Malayalam rendering.** Malayalam needs OpenType shaping: conjuncts
(ദ്യ, ണ്ണ, ക്ഷ), chillu letters (ർ, ൾ, ൻ), and pre-base vowel signs (േ, ൈ)
that render to the *left* of the consonant they follow in memory. Most Python
PDF libraries do no shaping and produce broken output that still looks like
text. This goes through MuPDF (PyMuPDF), which shapes via HarfBuzz.

**Fonts.** Noto Serif Malayalam ships with Windows 11 and is copied into
`rti_app/fonts/` on first run. On a machine without it, the script says so
and points at the Google Fonts page rather than falling back to a font that
would render incorrectly.

**Requirements.** `pymupdf` and `pyyaml`. Both already in use elsewhere in
this repo.

---

## Before you post

Two things the generator cannot check for you:

1. **The office address**, as above.
2. **The office designation on its own letterhead.** `വിദ്യാഭ്യാസ ഉപഡയറക്ടർ`
   and `ഉപജില്ലാ വിദ്യാഭ്യാസ ഓഫീസർ` are the standard forms, but offices vary
   in how they style it, and matching their own usage removes an excuse for
   misrouting.

Send by registered post with acknowledgement due, and keep the receipt — the
30-day clock runs from the date of receipt and you will need to prove it on
appeal. See `output/rti_toolkit.md` for the full timeline and escalation path.
