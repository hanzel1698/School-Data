# Estimating LP/UP division entitlement, and testing it against the department

Produced by `estimate_sanctioned_posts.py`. Enrolment re-crawled from Sametham
on 2026-08-15 (519 schools). Rules from the Kerala Education (Amendment) Rules,
2022, the staff-fixation ready reckoner and the strength-wise division tables
(all in `data/sources/`), cross-checked against muralipanamanna.in. Validated
against the DDE Malappuram staff-fixation order of 14.07.2026.

> The re-crawl reproduced the staff side **byte-identically** to the 14.08.2026
> crawl — all 519 schools, every designation count unchanged, 6,088 LP/UP posts
> both times. That independently confirms `output/staff_data_currency.md`:
> Sametham's staff data is not moving. `data/processed/malappuram_staff.csv` is
> therefore left as it was.

## What this is

Every staffing figure elsewhere in this repository is staff *in position*. A
vacant sanctioned post appears in no public source, so vacancies cannot be read
off Sametham. This approaches them from the other side: reconstruct how many
class divisions each school's enrolment earns, and compare against who is in
place.

The output is a signed **imbalance**, not a vacancy count.

## Headline

**The method works, and the district is close to balanced.**

| | Value |
|---|---:|
| Divisions earned (519 Government schools, LP+UP) | 6,050 |
| LP/UP teaching posts filled | 6,088 |
| **District imbalance** | **+38** |
| Schools estimated short | 184 |
| Schools balanced | 127 |
| Schools estimated in surplus | 208 |

Scored against the 134 schools where the department's own 2026-27 verdict is
known, the estimate separates them with **AUC 0.879** — the probability that a
school the department found surplus scores above one it sent teachers to.
Held-out cross-validation gives **0.855**, so this is not an artefact of
fitting.

A district that is roughly at entitlement, with surplus schools slightly
outnumbering short ones, is exactly the picture the department's own action
implies: it spent the 2026-27 fixation moving 91 teachers *out* of over-staffed
schools, not recruiting into empty ones.

## The rule, as the sources actually state it

**Statutory basis: KER Chapter XXIII rule 12, as substituted by the Kerala
Education (Amendment) Rules, 2022.** Sub-rule (1) requires the Educational
Officer to issue fixation orders through SAMANWAYA **by 15 July** each year,

> "after finalizing the number of **divisions in each class** based on the
> strength of pupils on the roll having Unique Identification Number (UID) as
> on the sixth working day from the reopening day in June. The UID strength
> shall be taken from Sampoorna."

Three things fall out of that single sentence:

- **"Divisions in each class"** settles the per-standard question in the rule
  itself, not just empirically.
- The basis is **UID strength on the sixth working day, from Sampoorna** —
  confirming the enrolment we compute on is the same input the department used.
- The **15 July** deadline is why the DDE order is dated 14.07.2026 and takes
  effect the 15th. It was issued on the statutory date.

The same amendment inserts **rule 23A**: the teacher-pupil ratio for standards
I–VIII is the **SCHEDULE to the RTE Act, 2009**, and confines the old rule 23
class maximum to standards IX–X. That schedule is the shape of the LP table:

| LP strength | Divisions |
|---|---:|
| 1–30 | 1 |
| 31–60 | 2 |
| 61–90 | 3 |
| 91–120 | 4 |
| **121–200** | **5** |
| above 200 | ratio not exceeding 1:40 |

So the plateau across 121–200 and the switch to 40-pupil steps are not
transcription quirks — they are the RTE Schedule, incorporated into KER in
2022. UP is a clean 1:35 throughout; HS is 1:45 and out of scope.

The schedule's minimum-teacher floors (two for a primary section; one per class
plus subject minimums for upper primary) were tested and **never bind** — a
school with four LP standards already earns at least four divisions. That the
floors are automatically satisfied is a further check that per-standard is the
right granularity.

The ratio bands **do not line up with the sections**: 1:30 covers **standards
I–V** and 1:35 covers **VI–VIII**, so standard 5 sits in the UP section but
forms divisions at the LP ratio (AUC 0.879 against 0.878 for a naive section
split).

## Three corrections to the method as originally proposed — one of them to my own

### 1. Divisions are counted per standard, not per section total

Your step 2 proposed dividing total section enrolment. That scores **AUC
0.837** and puts the district 1,033 posts in surplus. Counting each standard
separately scores **0.879** and puts it at +38. Divisions are physical classes
of one standard; the arithmetic has to follow that.

### 2. But NOT per medium — I was wrong about this

I previously argued that because Kerala forms divisions medium-wise, and
Sametham publishes a Standard × Medium table, the calculation had to split on
medium. **The department's decisions say otherwise.** Splitting by medium
scores **0.862** against 0.879, and pushes the district to a 524-post shortfall
that the 2026-27 redeployment plainly contradicts.

I over-modelled. The earlier claim that ignoring medium "understates
entitlement by 31%" was measuring the gap between two wrong models — the
section-total method against the medium-wise one. Against the correct
per-standard method the medium split *overstates* entitlement. Your original
instinct to work from plain enrolment was closer than my refinement; it just
needed to be per standard rather than per section. The variant is kept behind
`--medium-wise` since it is a reasonable hypothesis that the data rejects.

### 3. The shared posts count against divisions

Excluding the headmaster and the Arabic/Urdu/Hindi language teachers drops
separation to **0.827**. The reckoner explains why: language posts are
sanctioned on **periods per division** (Sanskrit/Arabic/Urdu 4 periods each in
standards I–IV; Hindi 2–3 periods in V–VII), with 4–14 periods giving one
part-time post and 15–28 one full-time post. They scale *with* divisions rather
than sitting outside them. So the 1,288 posts `malappuram_summary.md` cannot
split between LP and UP need no splitting here — they count in full against the
combined division total.

### And your step 4 concern was right

The difference is signed and both signs are common: 208 schools in surplus
against 184 short. Reporting only the negative side as "vacancies" would
mislabel more than half the schools that differ from entitlement.

## Validation against the department's decisions

| Department's verdict | Estimate: surplus | balanced | shortfall |
|---|---:|---:|---:|
| **Lost posts** (65) | **54** | 2 | 9 |
| **Received teachers** (69) | 8 | 16 | **45** |

- Sign agreement: **99 of 134 (74%)**
- Sign backwards: 17 (13%)
- Ranking separation: **AUC 0.879**; held-out CV **0.855**

Sweeping the ratios from 1:24 to 1:45 peaks at LP 1:31 / UP 1:35 (AUC 0.884).
The rule's own 1:30 / 1:35 scores 0.879 — inside the noise — so the rule is
kept rather than a fitted approximation to it. That the sweep lands on the
statutory values from a standing start is itself corroboration.

## A shortfall is not automatically a vacancy

The 2022 amendment adds the most important qualification to how the 184 short
schools should be read. Rule 12(3) gives ordinary fixation effect from 15 July,
but puts **additional divisions and additional posts in effect only from
1 October** — and only after the Educational Officer's surprise verification,
the Director's on-the-spot check, and a Government sanction due by 30 September
(sub-rules 4–6). The Explanatory Note is explicit that this machinery exists to
curb divisions created through bogus admissions.

So a school whose enrolment earns more divisions than it holds staff for may be
**mid-procedure rather than short**. Our snapshot sits before both dates:
enrolment from the sixth working day of June, staff from roughly the 27.06.2026
sync.

Rule 12(8) runs the other way: a fall in strength any time up to 31 January can
have divisions or posts **withdrawn**. Entitlement is a position in a process
that moves twice a year, not a standing figure.

## What is still not modelled

- **Effective strength.** The reckoner defines it as
  `Verified Strength + (Roll Strength × 5%)`, capped at roll strength. Sametham
  publishes one enrolment figure and does not say which it is. Adding a flat 5%
  moves the district by about 120 posts and *lowers* separation to 0.874,
  suggesting Sametham's figure already behaves like the effective one — but
  that is inference, not evidence.
- **Post protection.** A teacher whose post was abolished earlier is redeployed,
  not removed, so a school can hold protected staff above entitlement.
- **The pupils-opting threshold for language posts** — minimum 30 pupils in the
  UP section for one Hindi/Sanskrit/Arabic post. Sametham does not publish
  language options per school.
- **Relaxations** for hilly, coastal and single-teacher schools. Sametham
  carries `Is Hilly Area` and `Is Coastal Area` flags, so this is the most
  promising next refinement.

## How far to trust this

**Do** use it to rank schools by likely shortfall or surplus, and to size the
district position.

**Do not** cite a per-school figure as that school's vacancy count. The model
gets the sign wrong on 13% of schools where the answer is known, and carries no
model of protection or relaxation.

One caveat inherited from `output/staff_data_currency.md`: the staff side
predates the 15.07.2026 redeployment. That is what makes the validation valid,
but it means per-school imbalances describe the position *before* the
department acted.

Full ranked list: `data/processed/malappuram_division_estimate.csv`.

## Reproducing

```
python phase2_fetch.py                                # 519 pages, ~17 min
python estimate_sanctioned_posts.py                   # estimate and validate
python estimate_sanctioned_posts.py --calibrate       # sweep the ratios
python estimate_sanctioned_posts.py --medium-wise     # the rejected variant
```
