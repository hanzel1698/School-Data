# Sametham scraper — LP/UP teacher staffing, Malappuram Government schools

Extracts school-level teaching-staff data for Government schools in Malappuram
district from **Sametham**, KITE Kerala's public school data bank, and
aggregates it into LP-section and UP-section teacher counts.

The deliverable is a citable figure with the per-school data kept intact behind
it, so the aggregate is auditable rather than a bare number.

- Per-school data: [`data/processed/malappuram_staff.csv`](data/processed/malappuram_staff.csv)
- Aggregate with the arithmetic shown: [`output/malappuram_summary.md`](output/malappuram_summary.md)
- Discovery notes and endpoint audit: [`output/phase0_findings.md`](output/phase0_findings.md)

---

## The caveat that governs everything here

**Sametham reports staff *in position*, not *sanctioned posts*. These are
different numbers.**

Sanctioned LPST/UPST post counts are set annually through staff fixation, based
on sixth-working-day student strength. **A vacant sanctioned post does not
appear in Sametham at all.** Every figure this repo produces is therefore a
*floor* on the sanctioned establishment, never the establishment itself.

Sametham does expose a real **post-designation** breakdown — `L P School
Assistant`, `UP School Assistant`, `High School Assistant Mathematics` — rather
than a bare headcount, which puts it closer to a post count than expected. It
is still filled posts only.

Two further limits:

- **Higher-secondary staff are not published.** Every `Staff Details - HSS` and
  `- VHSS` table encountered returns `No Data Found!`.
- **Some records are visibly under-populated** — e.g. school 18501 reports
  `Total Employees - 2` for an entire high school. These are left as published;
  the summary reports how many schools carry no staff data at all.

## Why Sametham, and not Samanwaya or Sampoorna

| System | What it is | Used here |
|---|---|---|
| `sametham.kite.kerala.gov.in` | Public school data bank, published by the Kerala General Education Department for public and research use. No login. Exposes approved classes, students per class, and teaching/non-teaching staff counts. | **Yes — the only source touched** |
| `samanwaya.kite.kerala.gov.in` | Staff appointment management. Education-officer login. | **No** |
| `sampoorna.kite.kerala.gov.in` | School-level ERP. Headmaster/teacher login. | **No** |

Samanwaya and Sampoorna are credentialed internal systems and are out of scope.
They are never resolved, requested, or probed, and nothing in this codebase
references them. Samanwaya would hold sanctioned-post data, but it is not a
public source and is not an acceptable substitute.

### Crawl etiquette

- **1 request per 2 seconds, hard.** Single-threaded, no concurrency.
- `robots.txt` returns 404 — nothing is disallowed and no `Crawl-delay` is
  declared. The 2 s delay is our own courtesy limit.
- Descriptive `User-Agent` with a contact address, set in `config.yaml`.
- Retries on 5xx and timeouts with exponential backoff, 3 attempts, then the
  school is logged and skipped — one bad page never fails the run.
- Every request, status and skip reason is logged to `logs/scrape.log`.

The per-designation employee sub-pages (`/publicView/employees/…`) are
**deliberately not fetched**: they would multiply the crawl roughly 20× and
appear to list individual staff names, which this analysis does not need.

## How to run

Requires Python 3.11+ (developed on 3.14).

```bash
pip install httpx beautifulsoup4 pyyaml
```

```bash
python phase1_enumerate.py   # 1 request  — enumerate the district
python phase2_fetch.py       # 519 requests, ~18 min, resumable
python phase3_parse.py       # offline    — parse cache into the CSV
python phase4_summarise.py   # offline    — build the summary
```

`phase2_fetch.py --dry-run` reports what would be fetched without fetching.

**Phase 2 is cache-first and resumable.** Each response body is written to
`data/cache/{school_code}.html` before anything parses it, and a school already
in cache is never re-requested. Kill and restart it freely; re-running the
parser costs zero requests.

Verify the designation classifier:

```bash
python test_classify.py
```

Phase 0 discovery can be replayed stage by stage:

```bash
python phase0_discover.py robots      # robots.txt — the gate
python phase0_discover.py landscape   # home, advanced search, district probes
python phase0_discover.py schools     # sample detail pages
```

## Configuration

Everything tunable lives in [`config.yaml`](config.yaml) — base URL, district
id, rate limit, timeouts, retry policy, User-Agent, and paths. No literals are
scattered through the code.

The one non-obvious setting:

```yaml
working_set:
  skip_if_lowest_class_at_least: 8
```

Schools whose approved class range starts at class 8 have no LP (1–4) or UP
(5–7) section and so cannot hold LP/UP posts. This excludes 37 of Malappuram's
556 Government schools from fetching. They are still counted in the summary's
category table.

## How the LP/UP split is derived

**The structural catch:** a school has one staff table per *establishment*, and
the table's `- LP` / `- UP` / `- HS` suffix is the **school's category, not the
section of the staff inside it**. A school headed `Staff Details - HS`
routinely contains LP and UP posts. Trusting the header would report zero LP
and zero UP teachers for schools that plainly have both.

So section is read off the **designation**, in
[`scraper/classify.py`](scraper/classify.py), into five buckets:

| Bucket | Examples |
|---|---|
| `LP` | `L P School Assistant`, `Teacher (L P School) Gr II` |
| `UP` | `UP School Assistant`, `Teacher (U P School) Gr II` |
| `LP_UP_SHARED` | `Headmaster LP/UP`, `Teacher (LP/UP) - Arabic`, `Junior Arabic Teacher` |
| `HS_PLUS` | `High School Assistant …`, `P D Teacher`, `Workshop Instructor` |
| `NON_TEACHING` | `Clerk`, `Office Attendant`, `Part Time Menial` |

Rule order is load-bearing and the file documents why. Anything unmatched lands
in `UNCLASSIFIED` and is reported rather than absorbed into a bucket —
that fallback is what surfaced the site's `Mineal`/`Urudu` misspellings and the
`Junior Teacher Urdu` word-order variant.

`data/processed/designation_audit.csv` lists every designation encountered with
its bucket and post count, so the classification can be checked independently.

### Why LP and UP are reported as ranges

Some posts genuinely span both sections — chiefly the language teachers, who
are sanctioned on the number of students opting for that language and teach
across classes 1–7. Sametham exposes no field that splits them.

Rather than impute a split, they get their own column,
`teaching_staff_lp_up_shared`, and the summary reports:

- **LP + UP combined** — exact;
- **LP** and **UP** each as floor (section-specific only) to ceiling
  (section-specific + all shared).

The LP and UP ceilings cannot both be reached at once — they draw on the same
shared posts. Only the combined figure is simultaneously true.

Where a value is not exposed, the CSV holds an **empty cell, not a zero**.
Nothing is imputed, estimated, or back-filled from ratios: a null is a finding,
a fabricated number is a bug.

## Layout

```
config.yaml                     all tunables
scraper/
  config.py                     typed config loading
  fetcher.py                    rate limiting, retries, logging
  parse.py                      HTML → structured records
  classify.py                   designation → section bucket
phase0_discover.py              discovery/audit (staged)
phase1_enumerate.py             district list → JSONL
phase2_fetch.py                 detail pages → cache (resumable)
phase3_parse.py                 cache → CSV
phase4_summarise.py             CSV → summary markdown
test_classify.py                classifier assertions
data/
  raw/malappuram_schools.jsonl  all 1559 schools, working set flagged
  raw/fetch_manifest.jsonl      per-school url / fetched_at / status
  samples/                      Phase 0 raw HTML evidence
  cache/                        raw detail pages (gitignored)
  processed/                    the CSV outputs
output/                         findings note and summary
logs/scrape.log                 every request, status, skip reason
```

`data/cache/` is gitignored — the raw HTML dump is regenerable and does not
belong in git. `data/processed/` and `output/` are committed so the result is
reproducible from the repo without re-crawling.
