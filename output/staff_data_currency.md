# How current is Sametham's staff data? Dated against the 2026-27 staff fixation

Sources: DDE Malappuram order No. DDEMPM/7383/2026-A4 dated 14.07.2026
(`data/sources/DEPLOYMENT_ORDER_2026-27_LPST_UPST_DDE_MPM.pdf`) and the DGE/KITE
staff-fixation circulars for 2026-27
(`data/sources/staff_fixation_2026-27_circulars.md`). Live checks against
Sametham on 2026-08-15. Produced by `parse_deployment_order.py` and
`check_sametham_currency.py`.

## The headline

**Sametham's staff data is roughly seven weeks stale, and the staffing figures
in `output/malappuram_summary.md` predate the 2026-27 redeployment.**

Of eight redeployed teachers checked, **seven are still listed on the roster of
the school they were relieved from on 15.07.2026**, a month after the fact.
None appears unambiguously at the school they joined. The figures in this
repository therefore describe the establishment as it stood *before* the
2026-27 staff fixation took effect, not after.

## Why this could finally be measured

`output/phase0_findings.md` section 7 established that Sametham publishes no
update date for staff data — the homepage "Data updated on" stamp covers only
the school and student panels, HTTP `Last-modified` is a page-cache build time,
and no per-record timestamp exists. The recommendation was to measure the
currency externally instead.

The deployment order is exactly that measurement. It moves 91 named LPST and
UPST teachers between named schools on a known date, so each one is a dated,
checkable fact about who should appear on which roster.

## The fixation calendar, and where our snapshot sits in it

| Date | Event |
|---|---|
| 08.06.2026 | Sixth working day; student count frozen in Sampoorna at 5 PM |
| 18.06.2026 | Malappuram staff-fixation proposals confirmed in SAMANWAYA |
| 25.06.2026 | Deadline for validating student UIDs |
| **27.06.2026** | **Sametham's homepage "Data updated on" stamp** |
| 14.07.2026 | Teacher Bank list submitted; excess staff relieved; this order issued |
| **15.07.2026** | **91 Malappuram LPST/UPST teachers relieved and required to join their new schools the same day** |
| **14.08.2026** | **This project's crawl of Sametham** |
| 15.08.2026 | Live re-check performed for this document |

The homepage stamp of 27.06.2026 falls neatly after the 18–25 June SAMANWAYA
fixation window — consistent with Sametham refreshing once the fixation cycle
completes. It falls **before** the 15.07.2026 redeployment, which is what the
test below confirms.

## The test

For each sampled teacher, the employee roster of both the origin and the
destination school was fetched from Sametham and searched for their name. The
two sources transliterate differently (the order's `SAKKEENA BAHJATP H` is
Sametham's `SAKEENA BAHJATH P`), so matching allows for spelling drift.

| # | Teacher (as printed in the order) | Post | Origin | Still there? | Destination | Arrived? |
|---:|---|---|---|---|---|---|
| 1 | SHEENA.KP | LPST | 48049 | **yes** — SHEENA K P | 18525 | no |
| 3 | DEEPU P B | UPST | 48100 | not found | 48077 | no |
| 7 | RASHIDA CHELLAPPURATH VADAKKANIL | UPST | 18373 | **yes** | 19859 | no |
| 8 | SAKKEENA BAHJATP H | UPST | 18384 | **yes** — SAKEENA BAHJATH P | 18375 | no |
| 9 | ANU P | UPST | 18384 | **yes** — Anu P | 18375 | also listed |
| 10 | SABIRA KOPPILAN | LPST | 18302 | **yes** — SABINA KOPPILAN | 18318 | no |
| 12 | LIVYA L V | UPST | 18380 | **yes** | 18072 | no |
| 65 | JAMSHIYA.M | LPST | 48406 | **yes** | 48419 | no |

**7 of 8 still at the school they left. 0 of 8 unambiguously arrived.**

Case 9 is the only destination hit, and it is not evidence of a move: the same
teacher is still listed at the origin as well, and "Anu P" is a common enough
name that a same-named colleague at a 53-staff school is the likelier reading.
Case 3 is absent from both rosters — either a transliteration the matcher
missed, or a subsequent move; it does not affect the conclusion either way.

Sampled rather than exhaustive: confirming all 91 would mean about 180 roster
fetches, and the pattern does not change after the first few. The cases span
sub-districts, school types and both post categories.

## What the order adds beyond the currency question

**An authoritative LP/UP split.** Every row is classified LPST or UPST by the
department itself: **49 LPST, 42 UPST**. `output/malappuram_summary.md` has to
report LP and UP as ranges because 1288 of Sametham's posts carry designations
spanning both sections. The fixation process makes no such compromise, which
confirms the split exists administratively and is simply not exposed in
Sametham.

**A first measurement touching sanctioned posts.** 91 filled LPST/UPST posts
became excess in Malappuram in the 2026-27 fixation, across 68 losing schools,
redeployed into 71 receiving schools. This is a floor on posts lost, not the
figure itself — a sanctioned post that was already vacant when it was abolished
produces no redeployed teacher and so appears nowhere in this order.

Schools losing the most posts:

| Code | School | Posts lost |
|---|---|---:|
| 18578 | G.U.P.S. Pathappiriyam | 6 |
| 18471 | G.M.U.P.S. Chemmankadavu | 3 |
| 19002 | G M H S S C U Campus | 3 |
| 48049 | G G V H S S Wandoor | 2 |
| 18373 | G.M.U.P.S. Chirayil | 2 |

88 of the 91 teachers land in schools inside this project's 519-school working
set, so the order is almost entirely about the same population the summary
describes.

## This explains most of the "under-populated record" flags

`output/udise_crosscheck.md` flagged 10 schools whose LP/UP pupil-teacher ratio
was implausibly high, and could not tell whether that meant an incomplete
Sametham record or a genuinely under-staffed school. The deployment order
answers it:

| Code | School | LP/UP PTR | Teachers sent there on 15.07.2026 |
|---|---|---:|---:|
| 48425 | Mooleppadam GLPS | no teacher listed | 1 |
| 48129 | I G M M R S Nilambur | 96.5 | 0 |
| 18505 | G.L.P.S. Arukizhaya | 60.0 | 1 |
| 18021 | G B H S S Manjeri | 59.3 | 4 |
| 48047 | VMCGHSS Wandoor | 54.2 | 1 |
| 19453 | G. M. U. P. S. Venniyur | 50.2 | 0 |
| 18013 | G.B.H.S.S Malappuram | 48.0 | 1 |
| 19866 | GUPS Klari | 47.2 | 1 |
| 18072 | G.H.S.S. Kottappuram | 45.6 | 1 |
| 18438 | G.L.P.S. Melmuri North | 45.4 | 1 |

**8 of the 10 flagged schools received redeployed teachers**, including the one
school that showed LP/UP pupils and no LP/UP teacher at all. Only 71 of the 519
schools in the working set received anyone, a base rate of 13.7%, so 8 of 10 is
not chance (P(X≥8) ≈ 4×10⁻⁶ under a binomial with that rate).

The screen was picking up something real, and the department had already acted
on it. What it was detecting is best read as **a staffing shortfall that the
2026-27 fixation corrected on 15.07.2026, which Sametham had not yet
published** — not a parsing error, and not, in most cases, a permanently
under-staffed school.

## What to change in how the figures are cited

1. **Date the figures to the establishment before 15.07.2026.** "Staff in
   position as retrieved on 14 Aug 2026" is still literally true of the
   retrieval, but it invites the reader to assume the data is current to that
   date. It is not: it reflects roughly the 27.06.2026 sync, before the
   redeployment.
2. **The 6088 LP/UP figure is unaffected in aggregate.** The redeployment moves
   teachers between schools within the district; it does not add or remove them
   from the district total. Per-school figures for the 137 schools named in the
   order are stale.
3. **The sanctioned-post caveat stands, and now has a number attached.** At
   least 91 filled LPST/UPST posts were abolished in Malappuram for 2026-27.
   Vacant abolished posts remain invisible in every source used here.

## Reproducing

```
python parse_deployment_order.py    # order PDF -> data/processed/malappuram_deployment_2026_27.csv
python check_sametham_currency.py   # live roster checks -> data/processed/sametham_currency_cases.json
```

The second script fetches employee rosters, which name staff who are not in the
public order. Those are cached to `data/cache_rosters/` and git-ignored; only
the per-case verdict is committed.
