from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .storage import (
    ensure_store,
    find_entry,
    load_entries,
    summarize_month,
    summarize_week,
    upsert_entry,
)

app = typer.Typer(
    add_completion=False, help="A distinguished CLI butler at your service 🎩"
)
console = Console()
HAT = "🎩 "

# Butler's refined vocabulary
DRINK_ICONS = {
    0: "✨",  # Sparkles for abstinence
    1: "🥂",  # Single elegant glass
    2: "🍷",  # Wine glass
    3: "🍾",  # Champagne bottle (limit reached)
}


def format_drink_count(count: int) -> str:
    """Format drink count with appropriate icon and style."""
    if count == 0:
        return "✨ none at all"
    elif count == 1:
        return "🥂 a single libation"
    elif count == 2:
        return "🍷 a modest pair"
    elif count == 3:
        return "🍾 precisely at the limit"
    else:
        return f"🍻 {count} beverages ([red]exceeding propriety[/])"


def butler_address() -> str:
    """Polite butler address."""
    import random

    addresses = ["Sir/Madam", "Your Grace", "If I may", "Respectfully"]
    return random.choice(addresses)


def butler_phrase(address: str, message: str) -> str:
    """Format a butler's message with proper address handling."""
    if address:
        return f"{address}, {message}"
    else:
        return message


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
    """Record the day's libations with proper documentation."""
    day = resolve_day(yesterday)
    upsert_entry(day, n, note)

    day_phrase = "yesterday's records" if yesterday else "today's ledger"
    address = butler_address()

    if n == 0:
        message = (
            f"I've noted abstinence for [bold]{day}[/]. ✨ Most admirable restraint."
        )
        console.print(
            f"{HAT}{butler_phrase(address, message)}",
            style="green",
        )
    elif n <= 3:
        drink_desc = format_drink_count(n)
        message = f"{drink_desc} recorded in {day_phrase} for [bold]{day}[/]. Quite proper indeed."
        console.print(
            f"{HAT}{butler_phrase(address, message)}",
            style="green",
        )
    else:
        message = f"I must note [bold]{n} beverages[/] for [bold]{day}[/] - rather spirited! 🍻"
        console.print(
            f"{HAT}{butler_phrase(address, message)}",
            style="yellow",
        )
        console.print(
            "    [dim]Perhaps a gentle reminder that moderation is the hallmark of distinction.[/]",
            style="yellow",
        )


@app.command()
def add(
    n: int = typer.Argument(1, min=0, help="Increment by N (default 1)"),
    yesterday: bool = typer.Option(
        False, "--yesterday", "-y", help="Apply to yesterday"
    ),
):
    """Add refreshments to the day's tally with refined precision."""
    day = resolve_day(yesterday)
    entries = load_entries()
    existing = find_entry(entries, day)
    current = existing.count if (existing and existing.count is not None) else 0
    new = current + n
    upsert_entry(day, new)

    day_phrase = "yesterday's" if yesterday else "today's"
    address = butler_address()

    if new > 3 and current <= 3:
        message = f"we've now reached [bold]{new} beverages[/] in {day_phrase} ledger for [bold]{day}[/]."
        console.print(
            f"{HAT}{butler_phrase(address, message)}",
            style="yellow",
        )
        console.print(
            "    [dim]I do believe we've crossed into rather enthusiastic territory.[/]",
            style="yellow",
        )
    else:
        increment_text = f"+{n}" if n > 1 else "another"
        total_desc = format_drink_count(new)
        message = f"{increment_text} noted. {total_desc} in {day_phrase} register for [bold]{day}[/]."
        console.print(f"{HAT}{butler_phrase(address, message)}")


@app.command()
def week(
    date_: Optional[str] = typer.Option(
        None, "--date", "-d", help="Any date in the week (YYYY-MM-DD)"
    ),
):
    """Present a weekly summary with distinguished presentation."""
    anchor = date.fromisoformat(date_) if date_ else date.today()
    entries = load_entries()
    wk = summarize_week(entries, anchor)

    # Elegant table with butler's touch
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        title="📋 Weekly Libation Registry",
        title_style="bold blue",
    )
    table.add_column("Date", width=12, style="cyan")
    table.add_column("Beverages", justify="center", width=15)
    table.add_column("Personal Notes", overflow="fold", style="dim")

    d = wk["start"]
    while d <= wk["end"]:
        e = wk["days_map"].get(d)
        if e and e.count is not None:
            drinks = e.count
            if drinks == 0:
                disp = "✨ None"
                style = "green"
            elif drinks <= 3:
                icons = ["", "🥂", "🍷 🍷", "🍾 🍾 🍾"]
                disp = f"{icons[drinks]} ({drinks})" if drinks <= 3 else f"{drinks}"
                style = "green"
            else:
                disp = f"🍻 {drinks} [red](over)[/]"
                style = "yellow"
            note = e.note if e.note else "[dim]—[/]"
        else:
            disp = "[dim]— unrecorded —[/]"
            style = "dim"
            note = "[dim]—[/]"

        day_name = d.strftime("%A")
        date_str = f"{day_name}"
        table.add_row(date_str, disp, note, style=style)
        d = d + timedelta(days=1)

    # Distinguished summary panel
    compliance_icon = "✅" if wk["rule_ok"] else "⚠️"
    compliance_text = (
        "Within proper limits" if wk["rule_ok"] else "Exceeding recommendations"
    )

    period = f"Week commencing {wk['start'].strftime('%B %d')} through {wk['end'].strftime('%B %d, %Y')}"
    days_text = "day" if wk["drinking_days"] == 1 else "days"
    drinks_text = "beverage" if wk["total_drinks"] == 1 else "beverages"

    summary = (
        f"[bold]{period}[/]\n\n"
        f"📊 Drinking occasions: [bold]{wk['drinking_days']}[/] {days_text} (recommended ≤ 3)\n"
        f"🍷 Total consumption: [bold]{wk['total_drinks']}[/] {drinks_text}\n"
        f"{compliance_icon} Status: [bold]{compliance_text}[/]"
    )

    address = butler_address()
    message = "here is your weekly summary:"
    console.print(f"\n{HAT}{butler_phrase(address, message)}")
    console.print(table)
    console.print(
        Panel.fit(
            summary,
            title="📈 Weekly Assessment",
            border_style="green" if wk["rule_ok"] else "yellow",
            title_align="left",
        )
    )


@app.command()
def month(
    date_: Optional[str] = typer.Option(
        None, "--date", "-d", help="Any date in the month (YYYY-MM-DD)"
    ),
):
    """Present a distinguished monthly summary by week."""
    anchor = date.fromisoformat(date_) if date_ else date.today()
    entries = load_entries()
    month_data = summarize_month(entries, anchor)

    # Elegant table showing weekly compliance
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        title="📋 Monthly Libation Overview",
        title_style="bold blue",
    )
    table.add_column("Week", width=25, style="cyan")
    table.add_column("Status", justify="center", width=20)
    table.add_column("Days/Drinks", justify="center", width=15)
    table.add_column("Assessment", overflow="fold", style="dim")

    for i, week in enumerate(month_data["weeks"], 1):
        week_start = week["start"].strftime("%b %d")
        week_end = week["end"].strftime("%b %d")
        week_range = f"Week {i}: {week_start} - {week_end}"

        # Determine week status with proper distinction between no data and abstinence
        if week["recorded_days"] == 0:
            status = "📝 No Record"
            status_style = "dim"
            assessment = "No data recorded"
        elif week["drinking_days"] == 0:
            status = "✨ Completely Sober"
            status_style = "bold green"
            assessment = "Magnificent abstinence!"
        elif week["rule_ok"]:
            status = "✅ Compliant"
            status_style = "green"
            assessment = "Within proper limits"
        else:
            status = "⚠️ Exceeded"
            status_style = "yellow"
            assessment = "Rather spirited week"

        days_drinks = f"{week['drinking_days']}d / {week['total_drinks']}🍷"

        table.add_row(week_range, status, days_drinks, assessment, style=status_style)

    # Monthly summary panel
    month_name = month_data["month_start"].strftime("%B %Y")
    total_weeks = len(month_data["weeks"])
    no_record_weeks = sum(1 for w in month_data["weeks"] if w["recorded_days"] == 0)
    sober_weeks = sum(
        1
        for w in month_data["weeks"]
        if w["recorded_days"] > 0 and w["drinking_days"] == 0
    )
    compliant_weeks = sum(
        1 for w in month_data["weeks"] if w["recorded_days"] > 0 and w["rule_ok"]
    )
    exceeded_weeks = sum(
        1 for w in month_data["weeks"] if w["recorded_days"] > 0 and not w["rule_ok"]
    )

    # Calculate overall month status
    recorded_weeks = total_weeks - no_record_weeks
    if recorded_weeks == 0:
        month_status = "📝 No Records Available"
        month_style = "dim"
    elif sober_weeks == recorded_weeks:
        month_status = "✨ Completely Abstinent Month"
        month_style = "bold green"
    elif exceeded_weeks == 0 and recorded_weeks > 0:
        month_status = "✅ Fully Compliant Month"
        month_style = "green"
    else:
        month_status = "⚠️ Mixed Compliance Month"
        month_style = "yellow"

    days_text = "day" if month_data["total_drinking_days"] == 1 else "days"
    drinks_text = "beverage" if month_data["total_drinks"] == 1 else "beverages"

    summary = (
        f"[bold]{month_name}[/] - {month_status}\n\n"
        f"📊 Weekly breakdown:\n"
        f"   📝 No records: [bold]{no_record_weeks}[/] week(s)\n"
        f"   ✨ Completely sober: [bold]{sober_weeks}[/] week(s)\n"
        f"   ✅ Compliant drinking: [bold]{compliant_weeks - sober_weeks}[/] week(s)\n"
        f"   ⚠️ Exceeded limits: [bold]{exceeded_weeks}[/] week(s)\n\n"
        f"🍷 Monthly totals:\n"
        f"   Drinking occasions: [bold]{month_data['total_drinking_days']}[/] {days_text}\n"
        f"   Total consumption: [bold]{month_data['total_drinks']}[/] {drinks_text}\n"
        f"   Recorded abstinence: [bold]{month_data['sober_days']}[/] day(s)"
    )

    address = butler_address()
    message = f"behold your monthly summary for {month_name}:"
    console.print(f"\n{HAT}{butler_phrase(address, message)}")
    console.print(table)
    console.print(
        Panel.fit(
            summary,
            title="📈 Monthly Assessment",
            border_style=month_style.split()[-1] if " " in month_style else month_style,
            title_align="left",
        )
    )


@app.command()
def status():
    """Present a distinguished daily and weekly summary."""
    ensure_store()
    entries = load_entries()
    today = date.today()
    yest = today - timedelta(days=1)

    def count_for(d) -> int:
        e = find_entry(entries, d)
        return 0 if (e is None or e.count is None) else e.count

    c_today = count_for(today)
    c_yest = count_for(yest)

    week = summarize_week(entries, today)
    day_word = "occasion" if week["drinking_days"] == 1 else "occasions"
    drink_word = "beverage" if week["total_drinks"] == 1 else "beverages"

    address = butler_address()

    # Today's status with refined presentation
    today_status = format_drink_count(c_today)
    yest_status = format_drink_count(c_yest)

    message = "here is your current standing:"
    console.print(f"\n{HAT}{butler_phrase(address, message)}")
    console.print(f"   📅 Today's tally: [bold]{today_status}[/]")
    console.print(f"   📰 Yesterday's record: [bold]{yest_status}[/]")
    console.print(
        f"   📊 This week: [bold]{week['drinking_days']}[/] drinking {day_word}, [bold]{week['total_drinks']}[/] total {drink_word}"
    )

    if week["rule_ok"]:
        console.print(
            "   🎖️  [green]Exemplary adherence to proper limits! Most commendable.[/]"
        )
    else:
        console.print(
            "   🧐 [yellow]I must respectfully note we've exceeded recommended bounds this week.[/]"
        )
        console.print(
            "       [dim]Perhaps we might consider a more temperate approach going forward?[/]"
        )
