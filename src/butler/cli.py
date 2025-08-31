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

app = typer.Typer(add_completion=False, help="A dapper CLI butler that tracks your drinks 🎩")
console = Console()


def resolve_day(yesterday: bool) -> date:
    today = date.today()
    return today - timedelta(days=1) if yesterday else today


@app.command()
def set(
    n: int = typer.Argument(..., min=0, help="Number of drinks (0 or more)"),
    yesterday: bool = typer.Option(False, "--yesterday", "-y", help="Apply to yesterday"),
    note: Optional[str] = typer.Option(None, "--note", help="Optional note for the day"),
):
    """Set drinks for today (default) or yesterday."""
    day = resolve_day(yesterday)
    entry = upsert_entry(day, n, note)
    gt3 = n > 3
    hat = "🎩 "
    if gt3:
        console.print(f"{hat}A spirited evening! Marked [bold]{day}[/]: {n} (over the limit).", style="yellow")
    else:
        console.print(f"{hat}{n} logged for [bold]{day}[/]. Quite proper.")


@app.command()
def status():
    """Show today, yesterday, this week, and compliance."""
    ensure_store()
    entries = load_entries()
    today = date.today()
    yest = today - timedelta(days=1)

    e_today = find_entry(entries, today)
    e_yest = find_entry(entries, yest)

    week = summarize_week(entries, today)

    # Header panel
    header = "Butler Status — Rule of 3"
    hat = "🎩 "

    # Today & yesterday
    def fmt_entry(e: Optional[Entry]) -> str:
        if not e:
            return "none"
        c = e.count if e.count is not None else 0
        if c == 0:
            return "0"
        if c <= 3:
            return str(c)
        return f">3 ({c})"

    trow = f"Today: [bold]{fmt_entry(e_today)}[/]  |  Yesterday: [bold]{fmt_entry(e_yest)}[/]"

    # Week table
    table = Table(show_header=True, header_style="bold", box=box.SIMPLE)
    table.add_column("Date", width=12)
    table.add_column("Drinks", justify="right")
    table.add_column("Note", overflow="fold")

    d = week["start"]
    while d <= week["end"]:
        e = week["days_map"].get(d)
        if e:
            drinks = e.count if e.count is not None else 0
            disp = str(drinks) if drinks <= 3 else f">3 ({drinks})"
            note = e.note
        else:
            disp = "—"
            note = ""
        table.add_row(d.isoformat(), disp, note)
        d = d + timedelta(days=1)

    # Compliance summary
    badge = "✅ within limits" if week["rule_ok"] else "⚠ over limit"
    days = week["drinking_days"]
    total = week["total_drinks"]
    period = f"Week {week['start'].isoformat()} → {week['end'].isoformat()}"
    summary = f"{period}\nDrinking days: {days} (limit 3)\nTotal drinks: {total}\nRule of 3: {badge}"

    panel = Panel.fit(summary, title="Summary", border_style="green" if week["rule_ok"] else "red")

    console.print(f"{hat}{header}")
    console.print(trow)
    console.print(table)
    console.print(panel)
