# Getting the real numbers: sanctioned LP/UP posts and vacancies, Malappuram

Companion to `malappuram_summary.md`. That summary counts **filled** posts.
This document is about obtaining the **sanctioned** establishment and the
**vacancy** position, which Sametham does not publish and cannot be made to
publish.

> ### Scope of this request
>
> **Class-teacher posts only** — LP School Assistant (LPSA/LPST) and UP School
> Assistant (UPSA/UPST), at every grade (Grade II, Grade I, Senior Grade, Higher
> Grade). Deliberately **excluded**: language-teacher posts (Arabic, Sanskrit,
> Urdu, Hindi) and Headmaster LP/UP posts.
>
> This exclusion is clean, not approximate. In the scraped data every language
> and Headmaster post falls in the LP/UP-shared bucket; the LP-only and UP-only
> buckets contain **none**. So the scope drops the 1,288 shared posts entirely
> and leaves the two LP/UP figures untouched — and, usefully, **exact**:
>
> | | Filled posts |
> |---|---:|
> | LP School Assistant (all grades) | **3,202** |
> | UP School Assistant (all grades) | **1,598** |
> | **Total** | **4,800** |
>
> The LP/UP range problem described in the summary disappears under this scope.
> There is no shared column and no ceiling — every figure is a single exact
> number, which makes the reply far easier to check.

---

## 1. The one thing worth understanding first

There is no database anywhere that has a live "sanctioned vs. vacant" field per
school. What exists is an **annual administrative act** and a paper trail from it:

1. Schools report strength on the **sixth working day** of the academic year.
2. The department runs **staff fixation** (*thasthika nirnayam*) on that strength
   under the Kerala Education Rules, producing a **staff fixation order** —
   school-wise sanctioned post counts by designation. *This is the document you
   want.* It is the sanctioned establishment, in writing, signed, for that year.
   It will list language and Headmaster posts too; you simply ignore those
   columns, and the drafts below ask the PIO to restrict the reply to LPSA/UPSA.
3. Against each sanctioned post, someone is either substantively appointed, or
   the post is worked by a temporary hand, or it is empty. That state is tracked
   in a separate **vacancy position statement**, which is what gets reported to
   the Kerala PSC for recruitment.

So you are not asking for a report to be generated. You are asking for **copies
of two documents that already exist**. That distinction is the whole game — see §3.

---

## 2. "Vacant" officially means at least three different things

This is the single most common way an RTI on this subject comes back useless. If
you ask "how many posts are vacant," you will get one of these three numbers and
will have no way to tell which one:

| Sense | What it means | Typically smaller/larger |
|---|---|---|
| **A. Vacant on the establishment** | Sanctioned post with no substantive incumbent | The largest number |
| **B. Vacant but being worked** | Post held by a daily-wage / temporary / leave-vacancy appointee. Operationally "filled," still a recruitment vacancy | Subset of A |
| **C. Reported to KPSC** | The subset actually notified for recruitment | Usually the smallest |

C is systematically smaller than A in Kerala, and not because of under-reporting.
Vacancies in Government schools are first used to absorb **protected teachers**
(*samrakshitha adhyapakar*) — teachers whose posts vanished when divisions fell,
mostly in aided schools, who carry a redeployment claim. Those absorptions consume
real vacancies before anything reaches PSC.

**Therefore: ask for all three senses explicitly, as separate columns.** The drafts
below do this. A reply giving one undefined "vacant" figure is worth appealing.

Related trap: post **nomenclature**. Sametham writes `L P School Assistant` and
`UP School Assistant`; PSC notifications say LPST/UPST; office files say LPSA/UPSA.
Write all variants in the application so it cannot be deflected on terminology.

---

## 3. The framing rule that decides whether you get anything

RTI compels disclosure of **records that exist**. It does not compel a PIO to
compile, analyse, or answer questions — this is settled law (*CBSE v. Aditya
Bandopadhyay*, 2011). PIOs use it constantly to reject well-meaning applications.

- ✗ "How many LP teacher posts are vacant in Malappuram district?"
  → refusable as seeking creation of information.
- ✓ "Provide a copy of the staff fixation order/statement for the academic year
  2025–26 in respect of Government LP and UP schools under your jurisdiction,
  showing the school-wise number of sanctioned LP School Assistant and UP School
  Assistant posts."
  → a specific existing record; refusal is much harder to sustain.

Ask for the **records**. Do the arithmetic yourself afterwards. You already have
the filled-post side computed, so sanctioned − filled gives you vacancies
independent of whatever the PIO writes in a "vacant" column — which is a useful
cross-check on the reply itself.

**Second framing lever:** ask for it **in electronic form**. Section 2(j)(ii)
covers records held electronically and Section 7(9) requires information in the
form sought unless that disproportionately diverts resources. The staff fixation
data lives in Sampoorna (KITE's system), so a CSV/Excel export is a smaller burden
than photocopying. This also avoids a copying-fee bill for 519 schools' worth of
pages at the per-page rate.

---

## 4. Who actually holds it

Malappuram's Government LP/UP schools sit under **4 educational districts and 17
AEO sub-districts** (derived from your own scraped data):

| Educational District (DEO) | AEO sub-districts | Govt schools with LP/UP |
|---|---|---:|
| Malappuram | Kizhisseri, Kondotty, Malappuram, Manjeri, Mankada, Perinthalmanna | 176 |
| Thirurangadi | Parappanangadi, Tanur, Vengara | 98 |
| Tirur | Edappal, Kuttippuram, Ponnani, Tirur | 108 |
| Wandoor | Areacode, Melattur, Nilambur, Wandoor | 137 |
| **Total** | **17** | **519** |

Full per-AEO breakdown with student and filled-post counts: `rti_annexure_by_aeo.csv`.

| Office | Holds | Use it for |
|---|---|---|
| **AEO** (17 offices) | Staff fixation for LP/UP schools is done at this level. Most granular custodian. | The deflection-proof fallback |
| **DEO** (4 offices) | Consolidation across AEOs; HS establishment | Middle tier |
| **DDE Malappuram** (1 office) | Revenue-district consolidation | **Best single target** |
| **Directorate of General Education**, Thiruvananthapuram | State consolidation; the G.O.s and norms governing fixation | The rules, and appeals |
| **KITE**, Thiruvananthapuram | Sampoorna database incl. staff fixation module | Electronic export |
| **Kerala PSC** | Vacancies reported / advised / ranked lists | Sense **C**, and protected-teacher absorption |

### Recommended filing strategy

**Round 1 — two applications, ₹20 total:**
- **DDE Malappuram** — sanctioned + vacancy, school-wise, whole revenue district.
- **KPSC** — the recruitment-side numbers, which DDE will not have.

**Round 2, only if Round 1 is deflected or vague — 17 applications, ₹170:**
one per AEO. This is close to deflection-proof: each AEO holds only 19–52 schools,
so "disproportionate diversion of resources" under Section 7(9) is not a credible
refusal, and the AEO is the office that actually did the fixation. Costlier in
postage and tracking, far higher hit rate.

Do not start with the Directorate — it will almost certainly transfer under
Section 6(3), costing you a month. Start at DDE, which is senior enough to
consolidate and close enough to hold the records.

---

## 5. Attach the annexure

Two files are generated alongside this document:

- **`rti_annexure_schools.csv`** — all 519 Government schools: school code, UDISE
  code (where available), name, AEO sub-district, approved classes, students in
  1–4 and 5–7, and the currently filled **LPSA and UPSA** post counts, with
  **blank columns for the PIO to fill in** sanctioned and vacant.
- **`rti_annexure_by_aeo.csv`** — the same rolled up to 17 AEO rows, with a
  TOTAL row (519 / 3,202 / 1,598).
- **`rti_annexure_schools_ml.csv`** — same data, bilingual column headers, for
  use with the Malayalam drafts.

Attaching the school-code list converts your request from an open-ended research
question into a mechanical fill-in-the-blanks task against the department's own
primary key. It measurably raises the chance of a usable reply, and it makes a
vague reply obviously non-responsive at the appeal stage.

For a per-AEO filing, filter the CSV by the sub-district column and attach only
that AEO's rows.

---

## 6. Draft A — Deputy Director of Education, Malappuram

> To
> The State Public Information Officer,
> Office of the Deputy Director of Education,
> Malappuram, Kerala.
> *[Confirm the current office address before posting.]*
>
> **Sub: Application under the Right to Information Act, 2005**
>
> Sir/Madam,
>
> I request the following information in respect of **Government schools having
> an LP (Std. 1–4) and/or UP (Std. 5–7) section in Malappuram revenue district**.
> A list of 519 such schools with their school codes is enclosed as Annexure-I
> for ease of reference.
>
> 1. A copy of the **staff fixation order / statement (thasthika nirnayam)** for
>    the academic year **2025–26**, and separately for **2026–27** if already
>    issued, showing the **school-wise number of sanctioned posts** of **LP School
>    Assistant (LPSA / LPST)** and **UP School Assistant (UPSA / UPST)**, at all
>    grades of the said posts (Grade II, Grade I, Senior Grade and Higher Grade),
>    shown separately for each grade.
>
>    *I am **not** seeking information on language-teacher posts (Arabic,
>    Sanskrit, Urdu, Hindi) or on Headmaster LP/UP posts. Those may be omitted
>    from the reply.*
>
> 2. In respect of each such sanctioned post as on the date of this application,
>    a copy of the record showing, **school-wise and separately for each of the
>    following**:
>    a. the number of posts **filled by a substantive/regular appointee**;
>    b. the number of posts **vacant with no incumbent whatsoever**;
>    c. the number of posts **vacant but presently worked by a daily-wage,
>       temporary, or leave-vacancy appointee**.
>
> 3. A copy of the **vacancy position statement** in respect of the said posts
>    forwarded by this office, or by the District Educational Officers or
>    Assistant Educational Officers under it, to the **Kerala Public Service
>    Commission** during the period **1 January 2024 to the date of this
>    application**.
>
> 4. A copy of the record showing the number of **protected teachers**
>    (*samrakshitha adhyapakar*) absorbed against LP/UP posts in Government
>    schools in this district during the same period.
>
> 5. A copy of the **Government Order / rule** under which the staff fixation at
>    item 1 was carried out, including the pupil–teacher ratio and division
>    formation norms applied.
>
> **Form in which information is sought:** As the said information is held in
> electronic form in the Sampoorna system, I request it as a **spreadsheet
> (CSV/Excel) sent to the e-mail address below**, in terms of Section 2(j)(ii)
> read with Section 7(9) of the Act. If any part is not available electronically,
> attested photocopies of that part alone may be furnished.
>
> **Fee:** The prescribed application fee of ₹10 is enclosed. Kindly intimate any
> further fee payable under Section 7(3) before processing, along with the
> calculation.
>
> **If any part of this application pertains to another public authority**, kindly
> transfer that part within 5 days under Section 6(3) and intimate me.
>
> Name / Address / Phone / E-mail / Date / Signature
>
> Encl: Annexure-I (list of 519 schools); application fee.

---

## 7. Draft B — Assistant Educational Officer (per sub-district)

Same body as Draft A, with these changes:

- Address: **The State Public Information Officer, Office of the Assistant
  Educational Officer, `<sub-district>`** — one each for Kizhisseri, Kondotty,
  Malappuram, Manjeri, Mankada, Perinthalmanna, Parappanangadi, Tanur, Vengara,
  Edappal, Kuttippuram, Ponnani, Tirur, Areacode, Melattur, Nilambur, Wandoor.
- Scope line: "in respect of Government schools having an LP and/or UP section
  **in `<sub-district>` educational sub-district**."
- Annexure: only that sub-district's rows from `rti_annexure_schools.csv`
  (19–52 schools).
- Drop item 4 (protected teachers) — that is handled above AEO level.
- Add: "The number of schools concerned is `<N>`, as listed in the Annexure."
  Stating the small, bounded scope pre-empts a Section 7(9) refusal.

---

## 8. Draft C — Kerala Public Service Commission

> To
> The State Public Information Officer,
> Kerala Public Service Commission, Thiruvananthapuram.
>
> In respect of the posts of **LP School Teacher / LPSA / LPST** and **UP School
> Teacher / UPSA / UPST** in **Government schools in Malappuram district**, for
> the period **1 January 2022 to the date of this application**:
>
> 1. A copy of the record showing the **number of vacancies reported** to the
>    Commission by the appointing authority, year-wise.
> 2. A copy of the record showing the **number of candidates advised** against
>    those vacancies, year-wise.
> 3. The **current status of the ranked list(s)** for these posts for this
>    district — date of publication, date of expiry, total candidates in the
>    list, and number advised to date.
> 4. The number of reported vacancies, if any, **not filled and lapsed** on
>    expiry of the ranked list, year-wise.
>
> *(Same fee, form-of-information, and Section 6(3) paragraphs as Draft A.)*

---

## 9. Fee, filing and timeline

**Fee.** ₹10 application fee. In Kerala this is commonly paid by affixing a ₹10
**court fee stamp** to the application; cash at the office, DD, or treasury
chalan are the other routes. Applicants below the poverty line are exempt on
producing a copy of the BPL card. Confirm the mode currently accepted by that
specific office before posting — practice varies.

Additional fee under Section 7(3) applies for copies (a per-page rate for
photocopies, or the actual cost of a CD). Asking for e-mailed CSV largely avoids
this, which is the other reason to ask for electronic form.

**Filing.** Send by **registered post with acknowledgement due**, or deliver by
hand against a dated receipt. Keep the postal receipt and the AD card — the
30-day clock runs from receipt, and you will need to prove that date on appeal.
The central online RTI portal covers Union ministries only, not Kerala state
offices; whether a state online option is available for this department should be
verified rather than assumed.

**Timeline.**

| Stage | Limit |
|---|---|
| PIO reply | **30 days** from receipt |
| No reply by day 30 | Deemed refusal — and under **Section 7(6)** the information must then be supplied **free of charge** |
| First appeal | Within **30 days** of the reply or of the deemed refusal, to the First Appellate Authority in the same office (address it as "The First Appellate Authority, O/o …") |
| FAA order | Normally 30 days, extendable to 45 |
| Second appeal | Within **90 days**, to the **Kerala State Information Commission**, Thiruvananthapuram |

In the first appeal, note that the PIO is liable under **Section 20** to a penalty
of ₹250 per day up to ₹25,000 for refusing without reasonable cause or failing to
furnish within time. Stating it plainly, once, tends to be effective.

Realistic expectation: a good reply from a DDE or AEO in 30–45 days; a
second-appeal path can run 6–18 months, so file the parallel applications early
rather than escalating serially.

---

## 10. Routes that are faster than RTI, and worth doing in parallel

1. **Kerala Legislative Assembly questions** (`niyamasabha.nic.in`). District-wise
   teacher vacancy figures are tabled in answers to starred/unstarred questions
   fairly regularly. Past answers are published, dated, official and citable —
   search the education department's answers before filing anything. Getting an
   MLA to table a fresh question is often faster than an RTI appeal chain and
   yields a more quotable source.
2. **Kerala Budget — Detailed Budget Estimates**, under the General Education
   heads. Carries sanctioned post strength, but at state/head-of-account level,
   not per school. Good for a top-down sanity check on any district figure.
3. **Kerala Economic Review** (State Planning Board, annual) — education chapter,
   aggregate teacher numbers.
4. **KPSC annual report** — vacancy reporting and advice statistics.
5. **CAG audit reports** on Kerala's General Education department — performance
   audits routinely carry sanctioned-vs-men-in-position tables, already
   reconciled, with the department's own replies attached.
6. **Section 4(1)(b) proactive disclosure.** Staff strength is the kind of
   information a public authority is required to publish suo motu. A line in your
   application asking why it is not published under Section 4 is not a
   information request as such, but it does raise the cost of stonewalling.

---

## 11. When the reply arrives

Fill the returned figures into the blank columns of `rti_annexure_schools.csv` and
check three things:

1. **Does sanctioned ≥ filled, school by school?** Your filled counts come from
   Sametham. Any school where the PIO's sanctioned figure is *below* the published
   filled count is either a data error or an unreported excess post — both worth
   pursuing.
2. **Does sense A − sense B reconcile with the KPSC reply?** A large gap is the
   protected-teacher absorption, and is itself the finding.
3. **Do the four DEO subtotals add to the district total?** The summary's arithmetic
   check pattern applies equally here.

**Your benchmark is exact.** Under this scope there is no shared bucket and no
range. The filled side is **3,202 LPSA + 1,598 UPSA = 4,800**, and every
school-level figure in the annexure is a single number. Sanctioned minus these
gives vacancies directly.

**One thing to watch in the reply.** A PIO may simply send the whole staff
fixation order rather than the two columns asked for, in which case language and
Headmaster posts will be back in the sheet. Check the total before comparing: a
reply totalling around **4,800** is scoped as requested; one totalling around
**6,088** still carries the 1,288 language and Headmaster posts and must have
them stripped out first. Comparing an unstripped reply against the annexure will
show phantom surpluses in exactly the schools that have an Arabic or Hindi
teacher.
