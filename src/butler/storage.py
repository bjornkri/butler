
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


def upsert_entry(target_day: date, count: Optional[int], note: Optional[str] = None) -> Entry:
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
    rule_days_ok = drinking_days <= 3
    rule_per_day_ok = all((e.count or 0) <= 3 for e in subset)
    rule_ok = rule_days_ok and rule_per_day_ok
    return {
        "start": start,
        "end": end,
        "days_map": days_map,
        "drinking_days": drinking_days,
        "total_drinks": total_drinks,
        "rule_ok": rule_ok,
        "rule_days_ok": rule_days_ok,
        "rule_per_day_ok": rule_per_day_ok,
    }
