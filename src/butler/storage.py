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


def calculate_streaks(entries: list[Entry]) -> dict:
    """Calculate various drinking and compliance streaks."""
    if not entries:
        return {
            "current_abstinence": 0,
            "longest_abstinence": 0,
            "current_compliance_weeks": 0,
            "longest_compliance_weeks": 0,
            "days_since_over_limit": None,
            "days_since_rule_violation": None,
            "current_weekend_abstinence": 0,
            "perfect_weeks": 0
        }

    today = date.today()
    sorted_entries = sorted(entries, key=lambda e: e.day)

    # Current abstinence streak (from today backwards)
    current_abstinence = 0
    check_date = today
    while True:
        entry = find_entry(entries, check_date)
        if entry and entry.count is not None and entry.count > 0:
            break
        if entry and entry.count == 0:
            current_abstinence += 1
        elif entry is None and check_date <= today:
            # No record, but could be abstinent - be conservative
            pass
        check_date -= timedelta(days=1)
        if check_date < today - timedelta(days=365):  # Don't go back more than a year
            break

    # Longest abstinence streak (historical)
    longest_abstinence = 0
    temp_abstinence = 0
    last_date = None

    for entry in sorted_entries:
        # Handle gaps in data
        if last_date and (entry.day - last_date).days > 1:
            temp_abstinence = 0  # Reset on data gaps

        if entry.count is None or entry.count == 0:
            temp_abstinence += 1
            longest_abstinence = max(longest_abstinence, temp_abstinence)
        else:
            temp_abstinence = 0

        last_date = entry.day

    # Current compliance weeks streak
    current_compliance_weeks = 0
    current_week_start = today - timedelta(days=today.weekday())

    for i in range(104):  # Check up to 2 years back
        check_week_start = current_week_start - timedelta(days=7*i)
        week_summary = summarize_week(entries, check_week_start)

        # Only count weeks with recorded data
        if week_summary["recorded_days"] > 0 and week_summary["rule_ok"]:
            current_compliance_weeks += 1
        else:
            break

    # Longest compliance weeks streak (historical)
    longest_compliance_weeks = 0
    temp_compliance = 0

    # Go through all possible weeks
    earliest_date = min(e.day for e in entries) if entries else today
    week_start = earliest_date - timedelta(days=earliest_date.weekday())

    while week_start <= today:
        week_summary = summarize_week(entries, week_start)

        if week_summary["recorded_days"] > 0 and week_summary["rule_ok"]:
            temp_compliance += 1
            longest_compliance_weeks = max(longest_compliance_weeks, temp_compliance)
        else:
            temp_compliance = 0

        week_start += timedelta(days=7)

    # Days since last over daily limit (>3 drinks)
    days_since_over_limit = None
    check_date = today
    for i in range(365):  # Look back up to a year
        entry = find_entry(entries, check_date)
        if entry and entry.count is not None and entry.count > 3:
            days_since_over_limit = i
            break
        check_date -= timedelta(days=1)

    # Days since last rule violation
    days_since_rule_violation = None
    check_date = today
    for i in range(365):
        # Check if this week had any rule violations
        week_start = check_date - timedelta(days=check_date.weekday())
        week_summary = summarize_week(entries, week_start)

        if week_summary["recorded_days"] > 0 and not week_summary["rule_ok"]:
            days_since_rule_violation = i
            break
        check_date -= timedelta(days=1)

    # Weekend abstinence streak (consecutive alcohol-free weekends)
    weekend_abstinence_streak = 0

    # Find the most recent completed weekend
    # If today is Saturday or Sunday, look at this weekend; otherwise look at last weekend
    today_weekday = today.weekday()  # Monday=0, Sunday=6

    if today_weekday == 5:  # Saturday
        # This weekend is current weekend
        current_saturday = today
    elif today_weekday == 6:  # Sunday
        # This weekend is current weekend
        current_saturday = today - timedelta(days=1)
    else:
        # Look at most recent completed weekend
        days_back = today_weekday + 2  # How many days back to last Saturday
        current_saturday = today - timedelta(days=days_back)

    # Only look back for a reasonable number of weekends (52 weeks = 1 year)
    max_weekends = 52
    weekends_checked = 0

    while weekends_checked < max_weekends and current_saturday >= (today - timedelta(days=365)):
        # Check if this weekend was alcohol-free
        saturday_entry = find_entry(entries, current_saturday)
        sunday_entry = find_entry(entries, current_saturday + timedelta(days=1))

        # Only count as alcohol-free if both days have explicit 0 counts (not missing data)
        saturday_abstinent = saturday_entry and saturday_entry.count == 0
        sunday_abstinent = sunday_entry and sunday_entry.count == 0

        if saturday_abstinent and sunday_abstinent:
            weekend_abstinence_streak += 1
        else:
            break

        current_saturday -= timedelta(days=7)
        weekends_checked += 1

    # Total alcohol-free weekends (count all, not just consecutive)
    total_alcohol_free_weekends = 0
    if entries:
        earliest_date = min(e.day for e in entries)
        # Start from the first Saturday in our data range
        first_saturday = earliest_date - timedelta(days=earliest_date.weekday()) + timedelta(days=5)
        if first_saturday < earliest_date:
            first_saturday += timedelta(days=7)

        current_saturday = first_saturday
        while current_saturday <= today:
            saturday_entry = find_entry(entries, current_saturday)
            sunday_entry = find_entry(entries, current_saturday + timedelta(days=1))

            # Only count as alcohol-free if both days have explicit 0 counts
            saturday_abstinent = saturday_entry and saturday_entry.count == 0
            sunday_abstinent = sunday_entry and sunday_entry.count == 0

            if saturday_abstinent and sunday_abstinent:
                total_alcohol_free_weekends += 1

            current_saturday += timedelta(days=7)

    # Perfect weeks count (zero drinking days, full compliance)
    perfect_weeks = 0
    week_start = earliest_date - timedelta(days=earliest_date.weekday()) if entries else today

    while week_start <= today:
        week_summary = summarize_week(entries, week_start)

        if (week_summary["recorded_days"] > 0 and
            week_summary["drinking_days"] == 0 and
            week_summary["rule_ok"]):
            perfect_weeks += 1

        week_start += timedelta(days=7)

    return {
        "current_abstinence": current_abstinence,
        "longest_abstinence": longest_abstinence,
        "current_compliance_weeks": current_compliance_weeks,
        "longest_compliance_weeks": longest_compliance_weeks,
        "days_since_over_limit": days_since_over_limit,
        "days_since_rule_violation": days_since_rule_violation,
        "weekend_abstinence_streak": weekend_abstinence_streak,
        "total_alcohol_free_weekends": total_alcohol_free_weekends,
        "perfect_weeks": perfect_weeks
    }
