# Estimating LP/UP post entitlement from enrolment, and testing it against the department

Produced by `estimate_sanctioned_posts.py`. Enrolment re-crawled from Sametham
on 2026-08-15 (standard × medium, 519 schools). Validated against the DDE
Malappuram staff-fixation order of 14.07.2026.

> The re-crawl reproduced the staff side **byte-identically** to the 14.08.2026
> crawl — all 519 schools, every designation count unchanged, 6,088 LP/UP posts
> both times. That is a second, independent confirmation of the finding in
> `output/staff_data_currency.md`: Sametham's staff data is not moving, and has
> not moved since well before the 15.07.2026 redeployment. The committed
> `data/processed/malappuram_staff.csv` is therefore left as it was.

## What this is

Every staffing figure elsewhere in this repository is staff *in position*. A
vacant sanctioned post appears in no public source, so vacancies cannot be read
off Sametham. This approaches them from the other side: reconstruct how many
class divisions each school's enrolment earns, and compare against who is
actually in place.

The output is a signed **imbalance**, not a vacancy count — positive means more
teachers than divisions earn, negative means fewer. Both occur, and surplus was
the commoner case in Malappuram this year.

## Headline

**The method works.** Scored against 134 schools where the department's own
2026-27 verdict is known, the estimate separates them with **AUC 0.862** — the
probability that a school the department found surplus scores above one it sent
teachers to. Held-out cross-validation gives **0.838**, so this is not an
artefact of fitting.

| | Value |
|---|---:|
| Divisions earned (519 Government schools, LP+UP) | 6,621 |
| LP/UP teaching posts filled | 6,088 |
| **District imbalance** | **−533** |
| Schools estimated short | 269 |
| Schools estimated in surplus | 141 |
| Schools balanced | 109 |

The −533 is sensitive to the division-strength assumption in a way the ranking
is not: across the strengths that fit the department's decisions equally well
(LP 1:30–33, UP 1:35–40), the district figure ranges from **−277 to −533**.
Treat it as "a few hundred posts short across the district", not as 533.

## Three corrections to the method as originally proposed

### 1. Divisions are formed per standard *and* per medium

Not by dividing a section total. This is the single biggest arithmetic
difference:

| Method | Divisions |
|---|---:|
| Per standard × medium | 6,621 |
| Naive: section total ÷ strength | 5,055 |
| **Understatement** | **1,566 (31%)** |

GLPS Kuzhimanna, standard 1: 19 Malayalam-medium and 34 English-medium. That is
three divisions (1 + 2), not the two that 53 ÷ 30 gives. Applying the ratio to
the section total understates entitlement by nearly a third district-wide, and
understates it worst in exactly the small schools where the vacancy question
matters most.

### 2. 1:30 and 1:35 are right — but only if you count all LP/UP staff

The strengths were swept from 1:22 to 1:45 on both sections and scored against
the department's verdicts. The peak is LP 1:31 / UP 1:39 at AUC 0.867; the
conventional **1:30 and 1:35 score 0.862**, inside the noise. The assumed
figures are kept rather than fitted ones.

This only holds when the comparison counts **every LP/UP-attached teaching
post**, including the headmaster and the Arabic/Urdu/Hindi language teachers
that `malappuram_summary.md` reports as the shared column. Excluding them — on
the theory that only LP-specific and UP-specific designations hold divisions —
drops separation to 0.814 and leaves the model calling 25 of 65 known-surplus
schools a shortfall. In practice a Kerala LP/UP headmaster commonly holds a
division and language teachers take classes across standards 1–7; the fixation
decisions bear that out.

So the 1,288 shared posts that the summary cannot split between LP and UP do
not need splitting for this purpose. They count in full against the combined
LP+UP division total.

### 3. "Required − appointed" is an imbalance, not a vacancy count

The difference is signed and both signs are common: 141 schools estimated in
surplus against 269 short. Reporting the negative side alone as "vacancies"
would mislabel the 141, and the department's own order confirms surplus is
real — it moved 91 teachers *out* of over-staffed schools.

## Validation against the department's decisions

The order gives a verdict for 134 of the 519 schools: 65 lost posts (carrying
surplus) and 69 received redeployed teachers (posts available). Both the
fixation and this estimate run off the same sixth-working-day enrolment, and
the staff figures predate the 15.07.2026 redeployment, so the comparison is
aligned in time.

| Department's verdict | Estimate: surplus | balanced | shortfall |
|---|---:|---:|---:|
| **Lost posts** (65) | **41** | 8 | 16 |
| **Received teachers** (69) | 5 | 8 | **56** |

- Sign agreement: **97 of 134 (72%)**
- Sign backwards: 21 (16%)
- Ranking separation: **AUC 0.862**; held-out CV **0.838**

The extremes line up better than the aggregate suggests. The model's three
largest estimated surpluses are `18578 G.U.P.S. Pathappiriyam` (+7),
`18373 G.M.U.P.S. Chirayil` (+6) and `19441 G. M. U. P. S. Kakkad` (+5) — and
those are the department's biggest losers, at 6, 2 and 2 posts removed
respectively. Where the estimate is most confident, it is right.

## Where the residual error comes from

The 16 schools the department found surplus but the model calls short are the
informative failures. Candidate causes, none of which this model sees:

- **Post protection.** A teacher whose post was abolished in an earlier year is
  redeployed, not removed, so a school can hold protected staff above its
  current entitlement.
- **Language teachers' separate basis.** They are sanctioned on pupils opting
  for that language, so a school can hold one for reasons enrolment totals do
  not reveal — even though counting them improves the fit overall.
- **Relaxations** for hilly, coastal and single-teacher schools. Sametham
  carries `Is Hilly Area` and `Is Coastal Area` flags, so this is testable.
- **Specialist posts** (PD teacher, drawing, sewing), excluded from both sides
  here but which may absorb divisions in practice.

## Largest estimated shortfalls

| Code | School | Divisions | Staff | Imbalance | Department's verdict |
|---|---|---:|---:|---:|---|
| 19453 | G. M. U. P. S. Venniyur | 67 | 39 | −28 | — |
| 19866 | GUPS Klari | 65 | 40 | −25 | received teachers |
| 19439 | G. U. P. S. Ariyallur | 45 | 33 | −12 | received teachers |
| 18021 | G B H S S Manjeri | 20 | 10 | −10 | received teachers |
| 18204 | GLPS Kizhisseri | 33 | 23 | −10 | — |
| 48457 | Kurumbalangode GUPS | 28 | 18 | −10 | — |

`19453 G. M. U. P. S. Venniyur` is worth flagging: the largest estimated
shortfall in the district, and it also appeared in `output/udise_crosscheck.md`
as a pupil-teacher-ratio outlier — yet the redeployment did not reach it. On
this evidence it is genuinely under-staffed rather than a stale record.

Full ranked list: `data/processed/malappuram_division_estimate.csv`.

## How far to trust this

**Do** use it to rank schools by likely shortfall, and to size the district
problem to within a couple of hundred posts.

**Do not** cite a per-school figure as that school's vacancy count. The model
gets the sign wrong on 16% of schools where the answer is known, carries no
model of protection or relaxation, and rests on division strengths inferred
from 134 labelled schools rather than read from the KER text. Confirm the
strengths against the current rules before publishing any number from this.

One further caveat inherited from `output/staff_data_currency.md`: the staff
side of this comparison predates the 15.07.2026 redeployment. That is what
makes the validation valid, but it means the per-school imbalances describe the
position *before* the department acted, not the position today.

## Reproducing

```
python phase2_fetch.py                    # populate data/cache/ (519 pages, ~17 min)
python estimate_sanctioned_posts.py       # estimate and validate
python estimate_sanctioned_posts.py --calibrate       # sweep division strengths
python estimate_sanctioned_posts.py --exclude-shared  # the weaker variant
```
