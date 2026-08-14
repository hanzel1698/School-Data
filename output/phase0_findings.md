# Phase 0 — Discovery and audit findings

**Target:** `https://sametham.kite.kerala.gov.in/` only.
**Date of probe:** 2026-08-14
**Requests spent on Phase 0:** 12 (one was a TLS-handshake retry).
**Status:** Stopped for your review, as instructed. No bulk requests made.

Raw samples are in `data/samples/`. Nothing below is inferred from a source
other than those files.

---

## Headline

**Sametham exposes far more than the spec assumed.** Teaching staff is not a
single total and not a bare per-section headcount — it is a **full
post-designation breakdown** (`L P School Assistant -8`, `UP School Assistant
-5`, `High School Assistant Mathematics -1`, …), with each designation carrying
a stable numeric post code.

That means the LP/UP split you wanted is genuinely derivable rather than null.
It also means the whole job now hinges on one classification decision that I
want your ruling on before I build the parser — see
[Decision 1](#decision-1--how-to-treat-lpup-shared-posts).

There is also a **data-completeness problem** that will affect how the final
number should be read. See [Risk A](#risk-a--staff-data-is-visibly-incomplete-for-some-schools).

---

## 1. robots.txt

`GET /robots.txt` → **HTTP 404**, no robots.txt published.

Nothing is disallowed, no `Crawl-delay` is declared. Our configured 2.0 s
delay stands on its own as a courtesy limit, not as compliance with a stated
policy. Sample: `data/samples/robots_404.html`.

> Note: the very first request failed with a TLS handshake timeout and
> succeeded on retry. The host is occasionally slow to negotiate. The retry
> path is already exercised and working.

## 2. Rendering model and transport

**Server-rendered HTML throughout. There is no JSON API for the data we need.**

| Page | Evidence |
|---|---|
| `/` (home) | 4 static tables, no XHR markers in inline JS |
| `/search/advanced_search_interface` | form posts to `/search/advancedSearch`; inline JS has ajax **only** for cascading dropdowns |
| `/search/districtWiseSchools/10` | all 1 559 school rows present in the initial HTML |
| `/{school_code}` | all staff/student tables present in the initial HTML |

The ajax endpoints that do exist are dropdown-population helpers only — they
return option lists (`getEducationDistrictsAll`, `getSubDistrictsAll`,
`getAssembly/`, `getBlockPanchayath/`, `getParlamentary/`, `getcvals/`,
`getCMP/`). None of them carry staffing data, so there is **no JSON endpoint to
prefer over HTML parsing**. We parse HTML.

**Pagination: none.** The district list is a single unpaginated table — all
1 559 rows in one 2.0 MB response, no pager elements, no DataTables paging.
One request gets the whole district.

## 3. Malappuram district ID — confirmed = 10

Confirmed **empirically and twice over**, not on your say-so:

1. The site's own `<select name="rev_sub">` on the advanced-search page lists
   all 14 districts. `10 = Malappuram`, and `4 = Alappuzha` exactly as your
   note predicted.
2. `GET /search/districtWiseSchools/10` renders the heading
   **`Revenue District : Malappuram`**.

## 4. Endpoint table — corrected

| Purpose | Shape | Status |
|---|---|---|
| District school list (**recommended**) | `/search/districtWiseSchools/{district_id}` | **Confirmed.** All managements, 1 559 rows, unpaginated, includes a section prefix on the school code |
| District list, management-filtered | `/publicView/schoolsLists/all/dist/{district}/{ftype}` | **Confirmed.** `ftype`: `1`=Govt, `3`=Aided, `4`=Unaided, `All` |
| School detail | `/{school_code}` | **Confirmed** |
| Advanced search | `/search/advancedSearch` (POST) | Confirmed to exist; not needed |

Both district routes were fetched and **cross-check exactly**: the
`districtWiseSchools` table filtered client-side to `Finance Type = Government`
gives 556 rows, and the server-side `ftype=1` route independently returns 556
rows. I recommend `districtWiseSchools` as primary because one request yields
every management type plus a section label the other route lacks.

**Neither district route carries Education District or Sub District.** Those
two fields exist only on the school detail page, so the Phase 1 JSONL cannot be
fully populated until Phase 2 has run. I'll write Phase 1 with those columns
empty and backfill them in Phase 3 unless you'd rather I restructure.

### Malappuram composition (from the district list, 1 559 schools)

| Management | Schools |
|---|---:|
| Aided | 803 |
| **Government** | **556** |
| Unaided Recognised | 200 |
| **Total** | **1 559** |

Government schools by section label and approved class range:

| Section | Level | Count |
|---|---|---:|
| LP | 1 - 4 | 318 |
| LP | 1 - 5 | 30 |
| UP | 1 - 7 | 83 |
| UP | 5 -7 | 13 |
| HS | 1 - 12 | 21 |
| HS | 1 -10 | 19 |
| HS | 5 - 12 | 34 |
| HS | 8 - 12 | 35 |
| HS | 8 - 10 | 2 |
| HS | 5 - 10 | 1 |
| | **Total** | **556** |

Note the section label is only three values — `LP`, `UP`, `HS`. There is no
separate `HSS`/`VHSE` label in the list; higher-secondary schools appear as
`HS` and are distinguished by their level (`5 - 12`, `1 - 12`) and by a non-NIL
`HSS Code` / `VHSE Code` on the detail page. **Your Phase 4 category breakdown
of LPS/UPS/HS/HSS/VHSE therefore has to be derived**, not read off a field —
I propose deriving it from level + HSS/VHSE code presence.

## 5. School detail page — complete field inventory

Six schools sampled (three required + three to probe multi-section behaviour):

| Code | School | Level | Why |
|---|---|---|---|
| 18205 | GLPS Kuzhimanna | 1 - 4 | Govt LP |
| 18232 | G U P S Cheecode | 1 - 7 | Govt UP |
| 18150 | GHS Cheriyam Mankada | 1 -10 | Govt HS **with attached LP+UP** |
| 18010 | G.V.H.S.S. Pullanur | 1 - 12 | HSS + VHSE present |
| 18023 | G.G.H.S.S. Manjeri | 1 - 12 | HSS present |
| 18501 | Technical HS Manjeri | 8 - 10 | HS with no primary section |

Tables per page vary from **4 to 8**, so the parser must locate tables by
header text, never by index.

**Table 0 — Basic Information.** `School Code`, `HSS Code`, `VHSE Code`,
`School Name`, `School Type` (= management), `School Level` (= approved
classes), `School Address`, per-section phone/email (`LP/UP/HS Section
Phone`, `HSE Section Phone`), `UDISE Code`, `Panchayat/Municipality/
Corporation`, `Assembly Constituency`, `Revenue District`, `Education
District`, `Sub District`, `PIN Code`, `Parliament Constituency`, `Is Hilly
Area`, `Is Coastal Area`, `School Established Year`, `HSE Start Year`.

**Table 1 — Infrastructure Details (HS/LP/UP).** 51 numbered fields (area,
building, library, toilets, computers…). Not needed for this job.

**Tables 2..n — `Staff Details - {LP|UP|HS|HSS|VHSS}`.** The payload. See below.

**Remaining tables — `Students Details`,** per standard × medium (Malayalam /
English / Tamil / Kannada / ALL) × (Boys/Girls/Total), with a `Total` row.
Separate `Students Details of HSS` and `... of VHSS` tables where applicable.
Because it is per-standard, this yields **exact LP (std 1–4) and UP (std 5–7)
student counts**, not just a school total.

### Answers to your four specific questions

**(a) Single total, or broken down by section?**
Neither, and better than both: **broken down by individual post designation**,
with a `Total Employees - N` line per establishment.

**(b) Post-designation breakdown (LPST/UPST/HSA), or only headcount?**
**Full designation breakdown.** Each entry is a link:

```
<a href="/publicView/employees/18232/16B/5046">L P School Assistant -8</a>
<a href="/publicView/employees/18232/16B/8001">UP School Assistant -5</a>
```

The final path segment is a **stable numeric post code** (`5046` = L P School
Assistant, `8001` = UP School Assistant, `12396` = Teacher (U P School) Gr II,
`10000` = Headmaster LP/UP). The middle segment was `16B` on every school
sampled. I'll key classification on these codes and use the display name only
as a fallback — far more robust than string-matching designation text.

**(c) Management-type field?** Yes — `School Type` on the detail page and
`Finance Type` in the district list, plus server-side `ftype` filtering.

**(d) School-category field?** Partly. `LP`/`UP`/`HS` section prefix in the
district list, `School Level` for class range, `HSS Code`/`VHSE Code` for
higher-secondary presence. LPS/UPS/HS/HSS/VHSE must be derived from these.

### The structural catch that drives the parser design

**A school has one staff table per *establishment*, not per *section*, and the
table's own `- LP` / `- UP` / `- HS` suffix is the school's category, not the
section of the staff listed inside it.**

GHS Cheriyam Mankada (18150) has a single table headed `Staff Details - HS`
which contains, mixed together:

```
High School Assistant -1            L P School Assistant -4
UP School Assistant -4              L P School Assistant (Snr Gr) -4
Teacher (U P School) Gr II -3       L P School Assistant (Sel.Gr) -1
```

So **section attribution must come from the designation, never from the table
header.** A naive read of the header would credit 44 staff to "HS" and report
zero LP and zero UP teachers for a school that plainly has both.

`Staff Details - HSS` and `- VHSS` tables exist but returned **`No Data
Found!`** on every sampled school (they show only a Principal name). Higher
secondary staff are effectively **not published in Sametham**. That doesn't
affect LP/UP, but it must be stated in the summary.

---

## Decision 1 — how to treat LP/UP shared posts

This is the one thing I need from you. Observed designations sort into four
buckets, and the fourth is the problem:

**Unambiguously LP** — `L P School Assistant` (+ `Snr Gr`, `HG`, `Sel.Gr`),
`Teacher (L P School) Gr II`

**Unambiguously UP** — `UP School Assistant` (+ `Gr I`, `Grade I`),
`Teacher (U P School) Gr II`

**Unambiguously HS or above** — `High School Assistant` (+ ~20 subject/grade
variants), `Headmaster/Headmistress (High School)`, `P D Teacher`,
`Physical Education Teacher`, `Drawing Teacher`, `Sewing Teacher`

**Non-teaching** — `Clerk`, `Office Attendant` (+ grades), `Part Time Menial`, `FTM`

**Genuinely un-splittable between LP and UP:**

```
Headmaster LP/UP
Teacher (LP/UP) - Arabic (Grade I / Grade II)
Teacher (LP/UP) - Urdu (Grade II)
Teacher (LP/UP) - Hindi (Grade I / Grade II)
Junior Arabic Teacher Gr I / Gr II
Full time Arabic Teacher (+ Snr Gr)
Primary Teacher (Arabic) (Part Time with Full Time Benefit) HG
```

These are real teaching posts in LP/UP schools, but the post name itself spans
both sections — and language teachers in particular are sanctioned on a
separate basis (students opting for that language) and teach across standards
1–7. **There is no field on the page that splits them.** In the sampled UP
school 18232 they are 6 of 27 employees — not a rounding error.

Splitting them by any ratio would be exactly the imputation your spec forbids.

**My recommendation:** report **three** columns — `teaching_staff_lp`,
`teaching_staff_up`, and `teaching_staff_lp_up_shared` — and in the summary
give the LP and UP figures as a **range**: LP-specific alone as the floor, and
LP-specific + all shared as the ceiling. That keeps the number honest and
auditable, and you can still cite a single figure by picking a convention
explicitly.

| Option | What you'd cite |
|---|---|
| **A (recommended)** | Three columns; LP and UP each reported as a floor–ceiling range |
| B | Shared posts as their own category, excluded from both LP and UP |
| C | Assign the LP/UP language teachers wholly to LP (they mostly sit in LP-heavy schools) — **this is an assumption, not data** |

---

## Risk A — staff data is visibly incomplete for some schools

Two of six sampled schools have implausibly low staff:

- **18501 Technical High School Manjeri** — `Total Employees - 2` for an entire
  high school.
- **18023 G.G.H.S.S. Manjeri** — 31 employees, of which 3 LPSA and 1 UPSA, for
  a 1–12 girls' HSS.

These look like under-populated records rather than real establishments. I
cannot tell from six samples how widespread this is. **Proposal:** during
Phase 3 I'll compute a completeness flag per school (staff table present /
absent / `No Data Found!` / total below a plausibility floor given student
count) and report the affected share in Phase 4, exactly as you asked for the
null count. That turns the problem into a documented finding.

## Risk B — the staff-in-position caveat is worse than stated

Your caveat is right and I'll carry it. Two things sharpen it:

1. Sametham gives **staff in position by post designation** — genuinely closer
   to a post count than a bare headcount, which is good news. But a **vacant
   sanctioned post still does not appear**, so this remains a floor on
   sanctioned LPST/UPST, never the sanctioned number itself.
2. Combined with Risk A, the figure is a floor with an unknown-but-measurable
   amount of missing data underneath it.

## Decision 2 — the per-designation employee sub-pages

Each designation links to `/publicView/employees/{code}/16B/{post_id}`. I have
**not** fetched any of these. Two reasons: they would multiply the crawl by
roughly 20× (~25 000 requests, ~14 hours at our rate limit), and given the
school page already names the Head Master and Principal, these sub-pages
plausibly list **individual staff names** — personal data we don't need, since
the counts are already on the school page.

**Recommendation: don't fetch them.** Say so if you want one sampled to
confirm what's behind the link.

---

## 6. Request-count estimate for the full crawl

Rate limit 2.0 s/request, single-threaded.

| Scope | Requests | At 2 s | Realistic wall clock |
|---|---:|---:|---:|
| Phase 1 district list | 1 | 2 s | ~10 s (2 MB response) |
| Phase 2 — Government only (556) | 556 | 18.5 min | **~25 min** |
| Phase 2 — Govt + Aided (1 359) | 1 359 | 45.3 min | **~60 min** |
| Phase 2 — all managements (1 559) | 1 559 | 52.0 min | **~70 min** |

Since Phase 4 asks for the aided comparison table, the working figure is
**≈1 360 requests / ~1 hour**. Adding unaided costs only ~10 min more if you
want the complete picture; your spec says keep them in the raw dump but out of
the working set, which the district list alone already satisfies.

Caching is per-school, so a re-run after a parser change costs **zero**
requests.

---

## What I need from you

1. **Decision 1** — LP/UP shared posts: option A, B, or C?
2. **Decision 2** — confirm we skip the per-employee sub-pages.
3. **Scope** — Govt + Aided (~1 h), or Govt only (~25 min) with aided deferred?
4. Confirm the contact email in the User-Agent. It's currently
   `hanzel.h.fernandez@gmail.com`, taken from your git/session identity —
   change it in `config.yaml` if you'd rather use another.

On your go-ahead I'll build Phases 1–3 and run the crawl.

## Scope compliance

Only `sametham.kite.kerala.gov.in` was contacted. `samanwaya.kite.kerala.gov.in`
and `sampoorna.kite.kerala.gov.in` were never resolved, requested, or probed,
and nothing in the code references them.
