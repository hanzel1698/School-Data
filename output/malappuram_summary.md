# Malappuram — LP and UP teaching staff in Government schools

Source: Sametham, KITE Kerala (`sametham.kite.kerala.gov.in`). Generated 2026-08-14 10:27 UTC.

## Read this first

These are **staff in position, not sanctioned posts.** Sanctioned LPST/UPST
post counts are set annually through staff fixation based on sixth-working-day
student strength. **A vacant sanctioned post does not appear in Sametham at
all**, so every figure below is a *floor* on the sanctioned establishment, never
the establishment itself.

Sametham does expose a genuine **post-designation** breakdown (`L P School
Assistant`, `UP School Assistant`, …), so these are designation-level counts
rather than raw headcount. That is closer to a post count than the task
anticipated — but it is still filled posts only.

**These figures predate the 2026-27 staff fixation.** Sametham's staff data was
dated externally on 2026-08-15 against a redeployment order of known effect
(`output/staff_data_currency.md`): 91 Malappuram LPST/UPST teachers moved school
on 15.07.2026, and seven of eight sampled are still listed at the school they
left. So although this data was *retrieved* on 14 Aug 2026, it reflects roughly
the 27.06.2026 sync — before the fixation took effect. The district totals below
are unaffected, since the redeployment moves teachers within the district, but
**per-school figures for the 137 schools named in that order are out of date.**

## Headline

Across **519 Government schools** in Malappuram that have an LP
or UP section:

- **LP + UP teaching staff combined: 6088** — this figure is exact.
- **LP-section teaching staff: 3202 to 4490**
- **UP-section teaching staff: 1598 to 2886**

The ranges exist because **1288 posts are LP/UP shared** — chiefly
the language teachers (`Teacher (LP/UP) - Arabic`, `Junior Arabic Teacher`,
`Headmaster LP/UP`), who are sanctioned on the number of students opting for
that language and teach across classes 1–7. Sametham exposes no field that
splits them, and splitting them by a ratio would be imputation, so they are
reported as their own column.

**The LP and UP ceilings cannot both be reached at once** — they draw on the
same 1288 shared posts. Only the combined figure of
6088 is simultaneously true.

If you need one citable number, the defensible statement is:

> 6088 teachers are in position across the LP and UP sections of
> Malappuram's 519 Government schools that have such sections, of whom
> 3202 hold LP-specific posts, 1598 hold UP-specific posts, and
> 1288 hold posts spanning both.

## Scope

| | Schools |
|---|---:|
| All schools in Malappuram (all managements) | 1559 |
| Government schools | 556 |
| less: schools starting at class 8 (no LP/UP section possible) | −37 |
| Government schools with an LP or UP section | 519 |
| **Government schools in this analysis** | **519** |

Aided and unaided schools were enumerated into `data/raw/malappuram_schools.jsonl`
but deliberately **not fetched or aggregated** — this run was scoped to Government
schools only. There is therefore **no aided comparison table** in this summary.

Schools starting at class 8 were excluded because they have no LP (1–4) or UP
(5–7) section and so cannot hold LP/UP posts. They remain counted in the
category table below.

## Government schools by category

Sametham has no single category field — the district list carries only LP/UP/HS.
Category here is derived: VHSE or HSS if the school has a VHSE/HSS code, else
from the approved class range. Excluded schools have no detail page, so their
category is derived from the class range alone.

| Category | In analysis | Excluded (starts at class 8) | Total Government |
|---|---:|---:|---:|
| LPS | 318 | 0 | 318 |
| UPS | 126 | 0 | 126 |
| HS | 20 | 2 | 22 |
| HSS | 42 | 35 | 77 |
| VHSE | 13 | 0 | 13 |
| **Total** | **519** | **37** | **556** |

## The arithmetic

Both tables cover the same schools and must reach the same totals.

**Subtotals by school category**

| School Category | Schools | LP-only | UP-only | LP/UP shared | LP+UP total |
|---|---:|---:|---:|---:|---:|
| LPS | 318 | 1793 | 2 | 538 | 2333 |
| UPS | 126 | 1047 | 897 | 524 | 2468 |
| HS | 20 | 207 | 216 | 80 | 503 |
| HSS | 42 | 127 | 361 | 109 | 597 |
| VHSE | 13 | 28 | 122 | 37 | 187 |
| **Total** | **519** | **3202** | **1598** | **1288** | **6088** |

**Subtotals by educational district**

| Educational District | Schools | LP-only | UP-only | LP/UP shared | LP+UP total |
|---|---:|---:|---:|---:|---:|
| Malappuram | 176 | 1063 | 494 | 467 | 2024 |
| Thirurangadi | 98 | 769 | 412 | 259 | 1440 |
| Tirur | 108 | 541 | 284 | 213 | 1038 |
| Wandoor | 137 | 829 | 408 | 349 | 1586 |
| **Total** | **519** | **3202** | **1598** | **1288** | **6088** |

**Check:** LP-only + UP-only + shared = combined LP+UP total

    3202 + 1598 + 1288 = 6088

**Ranges:**

    LP floor   = LP-only                 = 3202
    LP ceiling = LP-only + shared        = 3202 + 1288 = 4490
    UP floor   = UP-only                 = 1598
    UP ceiling = UP-only + shared        = 1598 + 1288 = 2886

## Other staff in the same schools

Reported for completeness; not part of the LP/UP figure.

| Bucket | Posts |
|---|---:|
| HS and above teaching (HSA, PD teacher, vocational instructor, …) | 2656 |
| Non-teaching (clerk, office attendant, menial) | 725 |
| Unclassified by the designation rules | 4 |

Higher-secondary staff are **not published**: every `Staff Details - HSS` and
`- VHSS` table sampled returned `No Data Found!`. HSS/VHSE teachers are absent
from these totals entirely.

## Data completeness

| | Schools | Share |
|---|---:|---:|
| Staff data present | 519 | 100.0% |
| **Staff data absent — written as null, not zero** | **0** | **0.0%** |
| Total | 519 | 100.0% |


**Source inconsistency:** 2 UP-specific post(s) are listed
against schools approved only for classes 1–4, which have no UP section and
report zero UP students. These are published that way by Sametham and are
left as-is rather than corrected, since there is no basis for reassigning
them. They are counted in the UP column above.

**Unclassified posts: 4.** These are designations no rule
claims — pre-primary posts, which sit below LP, and post names carrying no
section marker at all (e.g. `Teacher Snr. Grd`). They are excluded from every
LP/UP figure rather than guessed into a bucket. See
`data/processed/designation_audit.csv` for the full list.

Beyond outright absence, some published records look **under-populated**: for
example school 18501 (Technical High School Manjeri) reports `Total Employees
- 2` for an entire high school. These are left as published.

**Cross-checked against UDISE+ on 2026-08-15** — see `output/udise_crosscheck.md`.
Two results bear on this figure:

1. **No systematic under-publication.** Sametham's own Kerala-wide Government
   LP+UP total (34 148) and UDISE+'s independently collected Kerala figure for
   Government primary/upper-primary schools (31 817) agree to within 7.3%, and
   the residual runs in the direction the definitions predict — Sametham counts
   by post designation, so LP/UP posts inside secondary schools are included,
   while UDISE counts by school category.
2. **Per-school completeness is narrowed, not resolved.** UDISE+ publishes no
   district or school rows on its public API, so no per-school join is
   possible. An internal pupil-teacher-ratio screen instead leaves 1 school
   with LP/UP pupils and no LP/UP teacher listed, and 9 schools above twice the
   district median ratio — a review shortlist, not a set of confirmed gaps.
   Ranked list in `data/processed/malappuram_ptr_check.csv`.

**Then largely explained, 2026-08-15** — see `output/staff_data_currency.md`.
**8 of those 10 flagged schools received redeployed LPST/UPST teachers** on
15.07.2026 under the DDE's staff-fixation order, against a base rate of 13.7%
(P ≈ 4×10⁻⁶). The screen was detecting a real shortfall that the department had
already corrected and Sametham had not yet published — not a parsing fault, and
in most cases not a permanently under-staffed school.

**A number for the sanctioned-post gap.** That same order redeploys **91 filled
LPST/UPST posts** abolished across 68 Malappuram schools in the 2026-27
fixation — 49 LPST and 42 UPST, the department's own LP/UP split. It is a floor
on posts lost: an abolished post that was already vacant produces no redeployed
teacher and appears in no source used here.

UDISE+ counts teachers in position too, so it does not soften the sanctioned-post
caveat at the top of this document.

Every school with staff data reconciles exactly against Sametham's own
`Total Employees` line — the parser is not dropping or double-counting rows.

## Student counts, for context only

Not used to derive any staff figure.

| | Students |
|---|---:|
| LP sections (classes 1–4) | 87492 |
| UP sections (classes 5–7) | 63480 |

## What this number is and is not

**It is:** the count of LP and UP teaching posts actually filled in Government
schools in Malappuram revenue district, as published by Sametham, classified by
post designation.

**It is not:**

- a count of *sanctioned* LPST/UPST posts — vacancies are invisible here;
- a teacher *headcount* usable for pupil–teacher ratio without care — part-time
  and shared posts are counted as posts;
- complete for higher secondary — HSS/VHSS staff are not published at all;
- inclusive of aided or unaided schools, which this run did not fetch;
- inclusive of Government schools starting at class 8, which have no LP/UP section.

## Reproducing this

```bash
python phase1_enumerate.py   # 1 request
python phase2_fetch.py       # 519 requests, resumable, ~18 min
python phase3_parse.py       # offline
python phase4_summarise.py   # offline
```

