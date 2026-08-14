"""HTML parsers for Sametham pages.

Parses defensively throughout: field presence is wildly inconsistent between
schools, table counts vary from 4 to 8, and single-teacher campuses and
multi-section campuses break naive selectors in opposite directions. Anything
that cannot be read is returned as None so it surfaces as a finding rather than
being quietly filled in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

from bs4 import BeautifulSoup, Tag

# "L P School Assistant (Snr Gr) -8" -> ("L P School Assistant (Snr Gr)", 8)
DESIGNATION_RE = re.compile(r"^(?P<name>.+?)\s*-\s*(?P<count>\d+)\s*$")
# "Total Employees - 27"
TOTAL_EMPLOYEES_RE = re.compile(r"Total\s+Employees\s*-\s*(\d+)", re.I)
# "/publicView/employees/18232/16B/5046" -> "5046"
POST_CODE_RE = re.compile(r"/publicView/employees/[^/]+/[^/]+/([^/?#]+)")
# "1 - 4", "1 -10", "5 -7", "8 - 12"
LEVEL_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")

NIL_VALUES = {"", "nil", "n/a", "na", "-", "none", "no data found!"}


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _is_nil(value: str | None) -> bool:
    return value is None or value.strip().lower() in NIL_VALUES


# --------------------------------------------------------------------------
# District-wide school list
# --------------------------------------------------------------------------


@dataclass
class DistrictRow:
    school_code: str
    school_name: str
    section_label: str
    block: str
    local_body: str
    parliamentary: str
    assembly: str
    management: str
    level: str
    phone: str
    latitude: str | None
    longitude: str | None


def parse_district_list(html: str) -> list[DistrictRow]:
    """Parse /search/districtWiseSchools/{id} into one row per school.

    The school-code cell carries a section prefix ("LP: 18205"); the location
    cell is either a maps link or the literal text "Not Available".
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("district list contained no <table>")

    rows: list[DistrictRow] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 12:
            continue

        text = [_clean(c.get_text(" ")) for c in cells]
        if text[1] in {"School Code", "#"} or text[0] == "#":
            continue

        raw_code = text[1]
        section_label, sep, code = raw_code.partition(":")
        if not sep:
            section_label, code = "", raw_code

        latitude = longitude = None
        location_link = cells[11].find("a", href=True)
        if location_link:
            coords = re.search(r"q=(-?\d+\.?\d*),(-?\d+\.?\d*)", location_link["href"])
            if coords:
                latitude, longitude = coords.group(1), coords.group(2)

        rows.append(
            DistrictRow(
                school_code=code.strip(),
                school_name=text[2],
                section_label=section_label.strip(),
                block=text[3],
                local_body=text[4],
                parliamentary=text[5],
                assembly=text[6],
                management=text[7],
                level=text[8],
                phone=text[9],
                latitude=latitude,
                longitude=longitude,
            )
        )

    if not rows:
        raise ValueError("district list table produced no data rows")
    return rows


# --------------------------------------------------------------------------
# School detail page
# --------------------------------------------------------------------------


@dataclass
class StaffEntry:
    """One designation line from a staff table."""

    designation: str
    count: int
    post_code: str | None
    establishment: str  # the table's own suffix: LP / UP / HS / HSS / VHSS


@dataclass
class SchoolDetail:
    school_code: str | None = None
    school_name: str | None = None
    management: str | None = None
    level: str | None = None
    hss_code: str | None = None
    vhse_code: str | None = None
    udise_code: str | None = None
    edu_district: str | None = None
    sub_district: str | None = None
    revenue_district: str | None = None
    local_body: str | None = None
    basic_info: dict[str, str] = field(default_factory=dict)
    staff: list[StaffEntry] = field(default_factory=list)
    reported_totals: dict[str, int] = field(default_factory=dict)
    students_by_standard: dict[str, int] = field(default_factory=dict)
    students_total: int | None = None
    staff_tables_seen: list[str] = field(default_factory=list)
    staff_tables_empty: list[str] = field(default_factory=list)

    @property
    def has_staff_data(self) -> bool:
        return bool(self.staff)


def _table_heading(table: Tag) -> str:
    """First header cell of a table, e.g. 'Staff Details - UP'."""
    head = table.find("th")
    return _clean(head.get_text(" ")) if head else ""


def _iter_label_value(table: Tag) -> Iterator[tuple[str, str]]:
    """Yield (label, value) from rows shaped as repeated label / ':' / value."""
    for tr in table.find_all("tr"):
        cells = [_clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        index = 0
        while index < len(cells):
            if index + 2 < len(cells) and cells[index + 1] == ":":
                label, value = cells[index], cells[index + 2]
                if label:
                    yield label, value
                index += 3
            elif index + 1 < len(cells) and cells[index + 1] != ":" and cells[index]:
                # Some rows drop the ':' separator entirely, e.g.
                # ['Panchayat/ Municipality/ Corporation', 'Kuzhimanna (P)']
                yield cells[index], cells[index + 1]
                index += 2
            else:
                index += 1


def _parse_staff_table(table: Tag, establishment: str) -> tuple[list[StaffEntry], int | None]:
    """Extract designation/count pairs and the reported Total Employees."""
    entries: list[StaffEntry] = []
    reported_total: int | None = None

    for anchor in table.find_all("a", href=True):
        label = _clean(anchor.get_text(" "))
        if not label:
            continue

        if TOTAL_EMPLOYEES_RE.search(label):
            # The total is also rendered as a link; capture it, don't count it
            # as a designation. It appears twice on some pages (once inline in
            # the final pair-row, once on its own row) - last write wins, and
            # both carry the same value.
            match = TOTAL_EMPLOYEES_RE.search(label)
            if match:
                reported_total = int(match.group(1))
            continue

        match = DESIGNATION_RE.match(label)
        if not match:
            continue

        post_code_match = POST_CODE_RE.search(anchor["href"])
        entries.append(
            StaffEntry(
                designation=_clean(match.group("name")),
                count=int(match.group("count")),
                post_code=post_code_match.group(1) if post_code_match else None,
                establishment=establishment,
            )
        )

    if reported_total is None:
        match = TOTAL_EMPLOYEES_RE.search(table.get_text(" "))
        if match:
            reported_total = int(match.group(1))

    return entries, reported_total


def _parse_students_table(table: Tag) -> tuple[dict[str, int], int | None]:
    """Read the per-standard 'ALL' total column from the students table.

    Layout is Standard | (medium x Boys/Girls/Total) x 4 | ALL Boys/Girls/Total,
    so the last cell of each data row is that standard's total across media.
    """
    by_standard: dict[str, int] = {}
    grand_total: int | None = None

    for tr in table.find_all("tr"):
        cells = [_clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        if len(cells) < 16:
            continue

        label = cells[0]
        last = cells[-1]
        if not last.isdigit():
            continue

        if label.lower() == "total":
            grand_total = int(last)
        elif label.isdigit():
            by_standard[label] = int(last)

    return by_standard, grand_total


def parse_school_detail(html: str) -> SchoolDetail:
    """Parse a /{school_code} page.

    Tables are located by their heading text, never by index: pages carry
    between 4 and 8 tables depending on whether HSS/VHSE sections exist.
    """
    soup = BeautifulSoup(html, "html.parser")
    detail = SchoolDetail()

    for table in soup.find_all("table"):
        heading = _table_heading(table)
        lowered = heading.lower()

        if lowered.startswith("basic information"):
            detail.basic_info = {
                label: value for label, value in _iter_label_value(table)
            }

        elif lowered.startswith("staff details"):
            establishment = heading.split("-", 1)[1].strip() if "-" in heading else ""
            detail.staff_tables_seen.append(establishment)
            entries, reported_total = _parse_staff_table(table, establishment)
            if entries:
                detail.staff.extend(entries)
            else:
                detail.staff_tables_empty.append(establishment)
            if reported_total is not None:
                detail.reported_totals[establishment] = reported_total

        elif lowered.startswith("students details"):
            # Only the main (std 1-10) table matters for LP/UP; the HSS/VHSS
            # student tables are a different population and are skipped.
            if "of hss" in lowered or "of vhss" in lowered:
                continue
            by_standard, total = _parse_students_table(table)
            if by_standard:
                detail.students_by_standard = by_standard
            if total is not None:
                detail.students_total = total

    info = detail.basic_info
    detail.school_code = info.get("School Code")
    detail.school_name = info.get("School Name")
    detail.management = info.get("School Type")
    detail.level = info.get("School Level")
    detail.hss_code = None if _is_nil(info.get("HSS Code")) else info.get("HSS Code")
    detail.vhse_code = None if _is_nil(info.get("VHSE Code")) else info.get("VHSE Code")
    detail.udise_code = info.get("UDISE Code")
    detail.edu_district = info.get("Education District")
    detail.sub_district = info.get("Sub District")
    detail.revenue_district = info.get("Revenue District")
    detail.local_body = info.get("Panchayat/ Municipality/ Corporation")

    return detail


def level_bounds(level: str | None) -> tuple[int, int] | None:
    """Parse '1 - 4' / '1 -10' / '5 -7' into (low, high). None if unreadable."""
    if not level:
        return None
    match = LEVEL_RE.match(level.replace("\xa0", " "))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
