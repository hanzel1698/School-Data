#!/usr/bin/env python3
"""Assertions for the designation classifier.

Cases are the real designation strings observed in data/samples/, plus the
spelling variants the site is known to mix ("UP School Assistant" vs
"U P School Assistant" vs "UP School Assistant Gr I").

    python test_classify.py
"""

from __future__ import annotations

from scraper.classify import Section, classify

CASES: list[tuple[str, Section]] = [
    # --- LP-only ---
    ("L P School Assistant -8", Section.LP),
    ("L P School Assistant", Section.LP),
    ("L P School Assistant (Snr Gr)", Section.LP),
    ("L P School Assistant HG", Section.LP),
    ("L P School Assistant (Sel.Gr)", Section.LP),
    ("LP School Assistant", Section.LP),
    ("Teacher (L P School) Gr II", Section.LP),
    # --- UP-only ---
    ("UP School Assistant", Section.UP),
    ("U P School Assistant", Section.UP),
    ("UP School Assistant Gr I", Section.UP),
    ("UP School Assistant Grade I", Section.UP),
    ("Teacher (U P School) Gr II", Section.UP),
    ("UP School Assistant Grade II", Section.UP),
    # Abbreviated with a scale glued on, no space before the bracket.
    ("LPSA(13210)", Section.LP),
    # --- LP/UP shared: the whole reason the third column exists ---
    ("Headmaster LP/UP", Section.LP_UP_SHARED),
    # Matches both the "headmistress" HS rule and the LP/UP rule; only the
    # rule ordering keeps it out of the HS bucket.
    ("Headmaster/Headmistress LP/UP", Section.LP_UP_SHARED),
    ("Teacher (LP/UP) - Arabic (Grade II)", Section.LP_UP_SHARED),
    ("Teacher (LP/UP) - Arabic (Grade I)", Section.LP_UP_SHARED),
    ("Teacher (LP/UP) - Urdu (Grade II)", Section.LP_UP_SHARED),
    ("Teacher (LP/UP) - Hindi (Grade I)", Section.LP_UP_SHARED),
    ("Teacher (LP/UP) - Hindi (Grade II)", Section.LP_UP_SHARED),
    ("Junior Arabic Teacher Gr II", Section.LP_UP_SHARED),
    ("Junior Arabic Teacher Gr I", Section.LP_UP_SHARED),
    ("Full time Arabic Teacher", Section.LP_UP_SHARED),
    ("Full time Arabic Teacher (Snr Gr)", Section.LP_UP_SHARED),
    ("Primary Teacher (Arabic) (Part Time with Full Time Benefit) HG", Section.LP_UP_SHARED),
    # --- HS and above ---
    ("High School Assistant", Section.HS_PLUS),
    ("High School Assistant Mathematics", Section.HS_PLUS),
    ("High School Assistant Natural Science (HG)", Section.HS_PLUS),
    ("High School Assistant Social Science(Sel Gr)", Section.HS_PLUS),
    ("High School Assistant Physical Science(Snr. Gr)", Section.HS_PLUS),
    ("High School Assistant Arabic (HG)", Section.HS_PLUS),
    ("High School Assistant Urdu", Section.HS_PLUS),
    ("High School Assistant (Urdu) (Part Time with Full Time Benefit)", Section.HS_PLUS),
    ("High School Assistant (Sanskrit) (Part Time)", Section.HS_PLUS),
    ("Headmaster/Headmistress (High School)", Section.HS_PLUS),
    ("P D Teacher", Section.HS_PLUS),
    ("P D Teacher (Senior Grade)", Section.HS_PLUS),
    ("P D Teacher (Selection Grade)", Section.HS_PLUS),
    ("P D Teacher (HG)", Section.HS_PLUS),
    ("Physical Education Teacher", Section.HS_PLUS),
    ("Physical Education Teacher (Grade-I)", Section.HS_PLUS),
    ("Physical Education Teacher(Before 11/04/2013)", Section.HS_PLUS),
    ("Drawing Teacher Gr II", Section.HS_PLUS),
    ("Sewing Teacher", Section.HS_PLUS),
    # --- variants found only once the full district was crawled ---
    ("Junior Teacher Urdu Gr II", Section.LP_UP_SHARED),
    ("Junior Teacher Urdu Gr I", Section.LP_UP_SHARED),
    ("Junior Teacher Urudu (8 Yrs HG)", Section.LP_UP_SHARED),
    ("Part-Time Primary Urudu Teacher", Section.LP_UP_SHARED),
    ("High School Asst (lower scale)", Section.HS_PLUS),
    ("Needle Work Teacher", Section.HS_PLUS),
    ("Workshop Instructor II HG", Section.HS_PLUS),
    ("Workshop Instructor / Instructor Gr II", Section.HS_PLUS),
    ("Workshop Instructor in Civil Engineering, Work experience (DTE)", Section.HS_PLUS),
    ("Lecturer DIET (32300 - 68700)", Section.HS_PLUS),
    # Language post with no "teacher" in the name.
    ("Lower Grade Arabic", Section.LP_UP_SHARED),
    ("Full time Hindi Teacher", Section.LP_UP_SHARED),
    ("Junior Hindi Teacher Gr II", Section.LP_UP_SHARED),
    ("Part Time Hindi teacher with FT Benefit", Section.LP_UP_SHARED),
    ("Part Time Language Teacher (Primary)", Section.LP_UP_SHARED),
    # A pre-primary post is below LP and must not land in the LP/UP bucket.
    ("Pre-Primary Teacher", Section.UNCLASSIFIED),
    # Genuinely unclassifiable: no section marker anywhere in the name. It must
    # stay visible rather than be absorbed into a bucket on a guess.
    ("Teacher Snr. Grd", Section.UNCLASSIFIED),
    # --- non-teaching ---
    ("Clerk", Section.NON_TEACHING),
    # The site spells "Menial" three ways and "Attendant" two ways.
    ("Part-Time Mineal (BP 2700)", Section.NON_TEACHING),
    ("Part-Time Mineal (BP 3000)", Section.NON_TEACHING),
    ("Part Time Meneal (4850/22 Yrs)", Section.NON_TEACHING),
    ("Office Attendent Sel Gr(9190-15780)", Section.NON_TEACHING),
    ("Ayah", Section.NON_TEACHING),
    ("Office Attendant", Section.NON_TEACHING),
    ("Office Attendant Gr II", Section.NON_TEACHING),
    ("Office Attendant Gr I (15 Yrs HG)", Section.NON_TEACHING),
    ("Office Attendant (8 Yrs HG)", Section.NON_TEACHING),
    ("Part Time Menial", Section.NON_TEACHING),
    ("FTM", Section.NON_TEACHING),
]


def main() -> int:
    failures: list[tuple[str, Section, Section, str]] = []
    for designation, expected in CASES:
        actual, note = classify(designation)
        if actual is not expected:
            failures.append((designation, expected, actual, note))

    print(f"{len(CASES) - len(failures)}/{len(CASES)} designation cases pass")

    if failures:
        print("\nFAILURES:")
        for designation, expected, actual, note in failures:
            print(f"  {designation!r}")
            print(f"    expected {expected.value}, got {actual.value} (rule: {note})")
        return 1

    # "Physical Education Teacher(Before 11/04/2013)" contains a date with
    # slashes; confirm normalisation did not turn it into an LP/UP match.
    section, _ = classify("Physical Education Teacher(Before 11/04/2013)")
    assert section is Section.HS_PLUS, section

    print("All designation classification cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
