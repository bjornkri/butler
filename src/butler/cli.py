from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .storage import (
    Entry,
    ensure_store,
    find_entry,
    load_entries,
    summarize_week,
    upsert_entry,
)

app = typer.Typer(
    add_completion=False, help="A dapper CLI butler that tracks your drinks 🎩"
)
console = Console()
HAT = "🎩 "


def resolve_day(yesterday: bool) -> date:
    today = date.today()
    return today - timedelta(days=1) if yesterday else today


@app.command()
def set(
    n: int = typer.Argument(..., min=0, help="Number of drinks (0 or more)"),
    yesterday: bool = typer.Option(
        False, "--yesterday", "-y", help="Apply to yesterday"
    ),
    note: Optional[str] = typer.Option(
        None, "--note", help="Optional note for the day"
    ),
):
    """Set drinks for today (default) or yesterday."""
    day = resolve_day(yesterday)
    upsert_entry(day, n, note)
    gt3 = n > 3
    if gt3:
        console.print(
            f"{HAT}A spirited evening! Marked [bold]{day}[/]: {n} (over the limit).",
            style="yellow",
        )
    else:
        console.print(f"{HAT}{n} logged for [bold]{day}[/]. Quite proper.")


@app.command()
def add(
    n: int = typer.Argument(1, min=0, help="Increment by N (default 1)"),
    yesterday: bool = typer.Option(
        False, "--yesterday", "-y", help="Apply to yesterday"
    ),
):
    """Add N drinks to today (or yesterday)."""
    day = resolve_day(yesterday)
    entries = load_entries()
    existing = find_entry(entries, day)
    current = existing.count if (existing and existing.count is not None) else 0
    new = current + n
    upsert_entry(day, new)
    if new > 3 and current <= 3:
        console.print(
            f"{HAT}Crossed the line today: now {new} (>3). A gentle tap on the wrist.",
            style="yellow",
        )
    else:
        console.print(f"{HAT}+{n} → {new} for [bold]{day}[/].")


@app.command()
def week(
    date_: Optional[str] = typer.Option(
        None, "--date", "-d", help="Any date in the week (YYYY-MM-DD)"
    ),
):
    """Show the week containing today (or --date)."""
    anchor = date.fromisoformat(date_) if date_ else date.today()
    entries = load_entries()
    wk = summarize_week(entries, anchor)

    table = Table(show_header=True, header_style="bold", box=box.SIMPLE)
    table.add_column("Date", width=12)
    table.add_column("Drinks", justify="right")
    table.add_column("Note", overflow="fold")

    d = wk["start"]
    while d <= wk["end"]:
        e = wk["days_map"].get(d)
        if e:
            drinks = e.count if e.count is not None else 0
            disp = str(drinks) if drinks <= 3 else f">3 ({drinks})"
            note = e.note
        else:
            disp = "—"
            note = ""
        table.add_row(d.isoformat(), disp, note)
        d = d + timedelta(days=1)

    badge = "✅ within limits" if wk["rule_ok"] else "⚠ over limit"
    period = f"Week {wk['start'].isoformat()} → {wk['end'].isoformat()}"
    days = wk["drinking_days"]
    total = wk["total_drinks"]
    summary = f"{period}\nDrinking days: {days} (limit 3)\nTotal drinks: {total}\nRule of 3: {badge}"
    console.print(f"{HAT}Week Summary")
    console.print(table)
    console.print(
        Panel.fit(
            summary, title="Summary", border_style="green" if wk["rule_ok"] else "red"
        )
    )


@app.command()
def status():
    """Show a concise summary for today/yesterday and weekly compliance."""
    ensure_store()
    entries = load_entries()
    today = date.today()
    yest = today - timedelta(days=1)

    def count_for(d) -> int:
        e = find_entry(entries, d)
        return 0 if (e is None or e.count is None) else e.count

    c_today = count_for(today)
    c_yest = count_for(yest)

    def fmt(n: int) -> str:
        if n == 0:
            return "none"
        if n <= 3:
            return f"{n} 🍷"
        return f">3 ({n})"

    week = summarize_week(entries, today)
    day_word = "day" if week["drinking_days"] == 1 else "days"
    drink_word = "drink" if week["total_drinks"] == 1 else "drinks"

    console.print(
        f"{HAT}Today's tally: [bold]{fmt(c_today)}[/] "
        f"| Yesterday: [bold]{fmt(c_yest)}[/]"
    )
    console.print(
        f"   This week: {week['drinking_days']} drinking {day_word}, total {week['total_drinks']} {drink_word}."
    )
    if week["rule_ok"]:
        console.print("   You're within the limits. Keep it up! ✅", style="green")
    else:
        console.print(
            "   You've exceeded the limits. A gentle reminder. ⚠", style="yellow"
        )
