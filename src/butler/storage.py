from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from rich.console import Console

console = Console()

DATA_DIR = Path.home() / ".butler"
CSV_PATH = DATA_DIR / "drinks.csv"


@dataclass
class Entry:
    day: date
    count: Optional[int]  # None means unknown
    note: str = ""

    @property
    def gt3(self) -> bool:
        return (self.count or 0) > 3

    def to_row(self) -> list[str]:
        c = "" if self.count is None else str(self.count)
        return [self.day.isoformat(), c, self.note]

    @staticmethod
    def header() -> list[str]:
        return ["date", "count", "note"]


def ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(Entry.header())


def load_entries() -> list[Entry]:
    ensure_store()
    entries: list[Entry] = []
    with CSV_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = date.fromisoformat(row.get("date", ""))
            except Exception:
                # skip malformed lines silently in MVP
                continue
            count_str = (row.get("count") or "").strip()
            note = (row.get("note") or "").strip()
            count = int(count_str) if count_str else None
            entries.append(Entry(day=d, count=count, note=note))
    return entries


def upsert_entry(
    target_day: date, count: Optional[int], note: Optional[str] = None
) -> Entry:
    entries = load_entries()
    idx = next((i for i, e in enumerate(entries) if e.day == target_day), None)
    if idx is None:
        entry = Entry(day=target_day, count=count, note=note or "")
        entries.append(entry)
    else:
        entry = entries[idx]
        if count is not None:
            entry.count = count
        if note is not None:
            entry.note = note
    # sort and write back
    entries.sort(key=lambda e: e.day)
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(Entry.header())
        for e in entries:
            writer.writerow(e.to_row())
    return entry


def find_entry(entries: Iterable[Entry], day: date) -> Optional[Entry]:
    for e in entries:
        if e.day == day:
            return e
    return None


def week_bounds(anchor: date) -> tuple[date, date]:
    # Monday-start week [monday, sunday]
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def summarize_week(entries: list[Entry], anchor: date) -> dict:
    start, end = week_bounds(anchor)
    subset = [e for e in entries if start <= e.day <= end]
    days_map = {e.day: e for e in subset}
    drinking_days = sum(1 for e in subset if (e.count or 0) > 0)
    total_drinks = sum((e.count or 0) for e in subset)
    recorded_days = sum(1 for e in subset if e.count is not None)
    abstinent_days = sum(1 for e in subset if e.count == 0)

    # Existing rules
    rule_days_ok = drinking_days <= 3
    rule_per_day_ok = all((e.count or 0) <= 3 for e in subset)

    # New gap rule: check for consecutive drinking days
    rule_gap_ok = check_gap_rule(entries, start, end)

    # Overall compliance requires all rules
    rule_ok = rule_days_ok and rule_per_day_ok and rule_gap_ok

    return {
        "start": start,
        "end": end,
        "days_map": days_map,
        "drinking_days": drinking_days,
        "total_drinks": total_drinks,
        "recorded_days": recorded_days,
        "abstinent_days": abstinent_days,
        "rule_ok": rule_ok,
        "rule_days_ok": rule_days_ok,
        "rule_per_day_ok": rule_per_day_ok,
        "rule_gap_ok": rule_gap_ok,
    }


def check_gap_rule(entries: list[Entry], week_start: date, week_end: date) -> bool:
    """
    Check the gap rule: at least one day between drinking days.

    Rules:
    1. If Monday has drinks, check if previous Sunday had drinks (cross-week)
    2. Check for consecutive drinking days within the week

    Returns True if compliant, False if consecutive drinking days found.
    """
    # Get all entries as a dict for easy lookup
    all_entries = {e.day: e for e in entries}

    def has_drinks(day: date) -> bool:
        entry = all_entries.get(day)
        return entry is not None and (entry.count or 0) > 0

    # Check cross-week boundary: Monday drinking + previous Sunday drinking
    monday = week_start  # week_start is always Monday
    if has_drinks(monday):
        previous_sunday = monday - timedelta(days=1)
        if has_drinks(previous_sunday):
            return False  # Non-compliant: consecutive Sunday-Monday drinking

    # Check consecutive days within the week
    current_day = week_start
    while current_day <= week_end:
        if has_drinks(current_day):
            next_day = current_day + timedelta(days=1)
            # Only check next day if it's still within the week
            if next_day <= week_end and has_drinks(next_day):
                return False  # Non-compliant: consecutive drinking days
        current_day += timedelta(days=1)

    return True  # Compliant: no consecutive drinking days found


def month_bounds(anchor: date) -> tuple[date, date]:
    """Get the first and last day of the month containing anchor date."""
    first_day = anchor.replace(day=1)
    if anchor.month == 12:
        last_day = anchor.replace(year=anchor.year + 1, month=1, day=1) - timedelta(
            days=1
        )
    else:
        last_day = anchor.replace(month=anchor.month + 1, day=1) - timedelta(days=1)
    return first_day, last_day


def summarize_month(entries: list[Entry], anchor: date) -> dict:
    """Summarize drinking data for the month containing the anchor date."""
    month_start, month_end = month_bounds(anchor)
    month_entries = [e for e in entries if month_start <= e.day <= month_end]

    # Group entries by week
    weeks = []
    current_monday = month_start - timedelta(days=month_start.weekday())

    while current_monday <= month_end:
        week_end = current_monday + timedelta(days=6)
        week_entries = [e for e in month_entries if current_monday <= e.day <= week_end]

        if week_entries or (current_monday <= month_end and week_end >= month_start):
            week_summary = summarize_week(entries, current_monday)
            # Only include if week overlaps with the month
            if (
                week_summary["start"] <= month_end
                and week_summary["end"] >= month_start
            ):
                weeks.append(week_summary)

        current_monday += timedelta(days=7)

    # Overall month statistics
    total_drinking_days = sum(1 for e in month_entries if (e.count or 0) > 0)
    total_drinks = sum((e.count or 0) for e in month_entries)
    sober_days = len([e for e in month_entries if e.count == 0])

    return {
        "month_start": month_start,
        "month_end": month_end,
        "weeks": weeks,
        "total_drinking_days": total_drinking_days,
        "total_drinks": total_drinks,
        "sober_days": sober_days,
        "total_days_recorded": len(month_entries),
    }
