from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .storage import (
    CSV_PATH,
    calculate_streaks,
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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """A distinguished CLI butler for managing your libations with the Rule of 3."""
    if ctx.invoked_subcommand is None:
        # Show distinguished welcome when no command is provided
        show_butler_welcome()


def show_butler_welcome():
    """Display a distinguished welcome message with available commands."""
    welcome_text = """[bold]🎩 Good day! Your distinguished butler at your service.[/]

[dim]I am here to assist you in maintaining proper conduct with the Rule of 3:[/]
[cyan]• No more than 3 drinking days per week[/]
[cyan]• No more than 3 drinks per day[/]
[cyan]• Always at least one day between drinking days[/]

[bold]Available Commands:[/]
[cyan]set <n>[/]     Record drinks for today
[cyan]add <n>[/]     Add drinks to today's tally
[cyan]status[/]      View current standing
[cyan]streaks[/]     Review achievement records
[cyan]week[/]        Review this week's conduct
[cyan]month[/]       Monthly compliance summary
[cyan]edit[/]        Open records in editor
[cyan]interactive[/] Launch interactive console"""

    panel = Panel(
        welcome_text,
        title="🎩 Butler",
        title_align="left",
        border_style="cyan",
        padding=(1, 2)
    )

    console.print(panel)
    console.print("\n[dim]For detailed help on any command: [cyan]butler <command> --help[/][/]")


# Butler's refined vocabulary
DRINK_ICONS = {
    0: "✨",  # Sparkles for abstinence
    1: "🍷",  # Single wine glass
    2: "🥂",  # Clinking glasses
    3: "🍾",  # Champagne bottle (limit reached)
}


def format_drink_count(count: int) -> str:
    """Format drink count with appropriate icon and style."""
    if count == 0:
        return f"{DRINK_ICONS[0]} none at all"
    elif count == 1:
        return f"{DRINK_ICONS[1]} a single libation"
    elif count == 2:
        return f"{DRINK_ICONS[2]} a modest pair"
    elif count == 3:
        return f"{DRINK_ICONS[3]} precisely at the limit"
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


def butler_notify(message: str, note: Optional[str] = None, style: str = "default") -> None:
    """Display a consistent butler notification for data changes."""
    address = butler_address()
    formatted_message = butler_phrase(address, message)

    if style == "moderate":
        console.print(f"{HAT}{formatted_message}", style="green")
    elif style == "caution":
        console.print(f"{HAT}{formatted_message}", style="yellow")
        if note:
            console.print(f"    [dim]{note}[/]", style="yellow")
    else:
        console.print(f"{HAT}{formatted_message}")


def butler_report(title: str, content, message: str = ""):
    """Display a consistent informational report with butler personality."""
    address = butler_address()

    if message:
        notification_text = f"{HAT}{butler_phrase(address, message)}"
        console.print(f"\n{notification_text}")

    # Create a panel with the report content
    panel = Panel(
        content,
        border_style="blue",
        padding=(1, 2),
        title=f"📊 {title}",
        title_align="left"
    )

    console.print(panel)


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

    if n == 0:
        message = f"[bold]abstinence[/b] noted for [bold]{day}[/]. ✨ Most admirable restraint."
        butler_notify(message, style="moderate")
    elif n <= 3:
        drink_desc = format_drink_count(n)
        message = f"[bold]{drink_desc}[/b] recorded for [bold]{day}[/]."
        butler_notify(message, style="moderate")
    else:
        message = f"[bold]{n} beverages[/] noted for [bold]{day}[/] - rather spirited! 🍻"
        note = "Perhaps a gentle reminder that moderation is the hallmark of distinction."
        butler_notify(message, note, style="caution")


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

    if new > 3 and current <= 3:
        message = f"we've now reached [bold]{new} beverages[/] for [bold]{day}[/]."
        note = "I do believe we've crossed into rather enthusiastic territory."
        butler_notify(message, note, style="caution")
    else:
        increment_text = f"+{n}" if n > 1 else "another"
        total_desc = format_drink_count(new)
        message = f"{increment_text} noted. {total_desc} for [bold]{day}[/]."
        style = "moderate" if new <= 3 else "caution"
        butler_notify(message, style=style)


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
                disp = "✨ Abstinent"
                style = "green"
            elif drinks <= 3:
                icons = [DRINK_ICONS[i] for i in range(0, 4)]
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

    # Display with butler_report, but need to print table separately
    address = butler_address()
    message = "here is your weekly summary:"
    console.print(f"\n{HAT}{butler_phrase(address, message)}")

    console.print(table)
    console.print("")  # Add some spacing

    # Create a panel for the summary
    panel = Panel(
        summary,
        border_style="blue",
        padding=(1, 2),
        title="📊 Weekly Assessment",
        title_align="left"
    )
    console.print(panel)


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

        # Check if this week includes today (incomplete week)
        today = date.today()
        is_current_week = week["start"] <= today <= week["end"]

        # Determine week status with proper distinction between no data and abstinence
        if week["recorded_days"] == 0:
            status = "📝 No Record"
            status_style = "dim"
            assessment = "No data recorded"
        elif week["drinking_days"] == 0:
            if is_current_week:
                status = "✨ Sober So Far"
                status_style = "green"
                assessment = "Abstinent this week (in progress)"
            else:
                status = "✨ Completely Sober"
                status_style = "bold green"
                assessment = "Magnificent abstinence!"
        elif week["rule_ok"]:
            if is_current_week:
                status = "✅ Compliant So Far"
                status_style = "green"
                assessment = "Following rules (week in progress)"
            else:
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

    # Check if this is the current month for proper counting
    today = date.today()
    month_start = month_data["month_start"]
    is_current_month = month_start.year == today.year and month_start.month == today.month

    # Count weeks with proper distinction for current/incomplete weeks
    completed_sober_weeks = 0
    sober_so_far_weeks = 0
    completed_compliant_weeks = 0
    compliant_so_far_weeks = 0

    for w in month_data["weeks"]:
        if w["recorded_days"] == 0:
            continue

        # Check if this week includes today (incomplete week)
        is_current_week = w["start"] <= today <= w["end"]

        if w["drinking_days"] == 0:
            if is_current_week:
                sober_so_far_weeks += 1
            else:
                completed_sober_weeks += 1
        elif w["rule_ok"]:
            if is_current_week:
                compliant_so_far_weeks += 1
            else:
                completed_compliant_weeks += 1

    # Total counts for legacy compatibility
    sober_weeks = completed_sober_weeks + sober_so_far_weeks
    compliant_weeks = sum(
        1 for w in month_data["weeks"] if w["recorded_days"] > 0 and w["rule_ok"]
    )
    exceeded_weeks = sum(
        1 for w in month_data["weeks"] if w["recorded_days"] > 0 and not w["rule_ok"]
    )

    # Calculate overall month status
    recorded_weeks = total_weeks - no_record_weeks

    # Check if this is the current month (incomplete)
    today = date.today()
    month_start = month_data["month_start"]
    is_current_month = month_start.year == today.year and month_start.month == today.month

    if recorded_weeks == 0:
        month_status = "📝 No Records Available"
        month_style = "dim"
    elif sober_weeks == recorded_weeks:
        if is_current_month:
            month_status = "✨ Abstinent So Far"
            month_style = "bold green"
        else:
            month_status = "✨ Completely Abstinent Month"
            month_style = "bold green"
    elif exceeded_weeks == 0 and recorded_weeks > 0:
        if is_current_month:
            month_status = "✅ Compliant So Far"
            month_style = "green"
        else:
            month_status = "✅ Fully Compliant Month"
            month_style = "green"
    else:
        if is_current_month:
            month_status = "⚠️ Mixed Month (So Far)"
            month_style = "yellow"
        else:
            month_status = "⚠️ Mixed Compliance Month"
            month_style = "yellow"

    days_text = "day" if month_data["total_drinking_days"] == 1 else "days"
    drinks_text = "beverage" if month_data["total_drinks"] == 1 else "beverages"

    # Build weekly breakdown text with proper distinction
    weekly_breakdown = f"📊 Weekly breakdown:\n"
    weekly_breakdown += f"   📝 No records: [bold]{no_record_weeks}[/] week(s)\n"

    if completed_sober_weeks > 0:
        weekly_breakdown += f"   ✨ Completely sober: [bold]{completed_sober_weeks}[/] week(s)\n"
    if sober_so_far_weeks > 0:
        weekly_breakdown += f"   ✨ Sober so far: [bold]{sober_so_far_weeks}[/] week(s)\n"

    # Calculate compliant drinking weeks (excluding sober weeks)
    non_sober_compliant = completed_compliant_weeks - completed_sober_weeks
    non_sober_compliant_so_far = compliant_so_far_weeks - sober_so_far_weeks

    if non_sober_compliant > 0:
        weekly_breakdown += f"   ✅ Compliant drinking: [bold]{non_sober_compliant}[/] week(s)\n"
    if non_sober_compliant_so_far > 0:
        weekly_breakdown += f"   ✅ Compliant so far: [bold]{non_sober_compliant_so_far}[/] week(s)\n"

    weekly_breakdown += f"   ⚠️ Exceeded limits: [bold]{exceeded_weeks}[/] week(s)"

    summary = (
        f"[bold]{month_name}[/] - {month_status}\n\n"
        f"{weekly_breakdown}\n\n"
        f"🍷 Monthly totals:\n"
        f"   Drinking occasions: [bold]{month_data['total_drinking_days']}[/] {days_text}\n"
        f"   Total consumption: [bold]{month_data['total_drinks']}[/] {drinks_text}\n"
        f"   Recorded abstinence: [bold]{month_data['sober_days']}[/] day(s)"
    )

    # Display with butler approach, but print table separately
    address = butler_address()
    message = f"behold your monthly summary for {month_name}:"
    console.print(f"\n{HAT}{butler_phrase(address, message)}")

    console.print(table)
    console.print("")  # Add some spacing

    # Create a panel for the summary
    panel = Panel(
        summary,
        border_style="blue",
        padding=(1, 2),
        title="📊 Monthly Assessment",
        title_align="left"
    )
    console.print(panel)


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

    # Today's status with refined presentation
    today_status = format_drink_count(c_today)
    yest_status = format_drink_count(c_yest)

    # Create status content
    status_content = (
        f"📅 Today's tally: [bold]{today_status}[/]\n"
        f"📰 Yesterday's record: [bold]{yest_status}[/]\n"
        f"📊 This week so far: [bold]{week['drinking_days']}[/] drinking {day_word}, [bold]{week['total_drinks']}[/] total {drink_word}\n\n"
    )

    if week["rule_ok"]:
        status_content += "🎖️  [green]This week: Exemplary adherence to proper limits! Most commendable.[/]"
    else:
        status_content += (
            "🧐 [yellow]This week: I must respectfully note we've exceeded recommended bounds.[/]\n"
            "    [dim]Perhaps we might consider a more temperate approach going forward?[/]"
        )

    butler_report("Current Standing", status_content, "here is your current standing:")


@app.command()
def streaks():
    """Present distinguished achievements and streaks in proper conduct."""
    ensure_store()
    entries = load_entries()
    streaks = calculate_streaks(entries)

    # Build streaks content with butler's refined presentation
    content = []

    # Primary achievement streaks
    content.append("🏆 [bold]Primary Achievements[/bold]")

    if streaks["current_abstinence"] > 0:
        days_text = "day" if streaks["current_abstinence"] == 1 else "days"
        content.append(f"   📅 Abstinence streak: [bold green]{streaks['current_abstinence']}[/] {days_text} [dim](completed days)[/]")
    else:
        content.append("   📅 Abstinence streak: [dim]Reset (drinking today or yesterday)[/]")

    if streaks["longest_abstinence"] > 0:
        days_text = "day" if streaks["longest_abstinence"] == 1 else "days"
        content.append(f"   🌟 Longest abstinence: [bold cyan]{streaks['longest_abstinence']}[/] {days_text}")

    # Days under daily limit (moved from milestone tracking, renamed for positive framing)
    if streaks["days_since_over_limit"] is not None:
        if streaks["days_since_over_limit"] == 0:
            content.append("   🍻 Days under daily limit: [yellow]Exceeded today[/]")
        else:
            days_text = "day" if streaks["days_since_over_limit"] == 1 else "days"
            content.append(f"   🍻 Days under daily limit: [bold green]{streaks['days_since_over_limit']}[/] {days_text}")
    else:
        content.append("   🍻 Days under daily limit: [bold green]Never exceeded in past year[/]")

    if streaks["current_compliance_weeks"] > 0:
        weeks_text = "week" if streaks["current_compliance_weeks"] == 1 else "weeks"
        content.append(f"   ✅ Compliance streak: [bold green]{streaks['current_compliance_weeks']}[/] {weeks_text} [dim](completed weeks)[/]")
    else:
        content.append("   ✅ Compliance streak: [yellow]Reset (this week or last week violated rules)[/]")

    if streaks["longest_compliance_weeks"] > 0:
        weeks_text = "week" if streaks["longest_compliance_weeks"] == 1 else "weeks"
        content.append(f"   🎖️  Best compliance run: [bold cyan]{streaks['longest_compliance_weeks']}[/] {weeks_text}")

    content.append("")

    # Special achievements (totals, not streaks)
    content.append("🌟 [bold]Special Achievements (Total Counts)[/bold]")

    content.append(f"   🏖️  Alcohol-free weekends: [bold cyan]{streaks['total_alcohol_free_weekends']}[/] weekend(s)")

    if streaks["perfect_weeks"] > 0:
        weeks_text = "week" if streaks["perfect_weeks"] == 1 else "weeks"
        content.append(f"   ✨ Perfect weeks (zero drinking): [bold cyan]{streaks['perfect_weeks']}[/] {weeks_text}")
    else:
        content.append("   ✨ Perfect weeks: [dim]No completely abstinent weeks recorded[/]")

    content.append("")

    # Butler's assessment
    content.append("💬 [bold]Butler's Assessment[/bold]")

    if streaks["current_compliance_weeks"] >= 8:
        content.append("   🎩 [bold green]Exemplary conduct! Your restraint brings me great pride.[/]")
    elif streaks["current_compliance_weeks"] >= 4:
        content.append("   🎩 [green]Commendable consistency in following the rules.[/]")
    elif streaks["current_compliance_weeks"] >= 1:
        content.append("   🎩 [green]Good progress in maintaining proper standards.[/]")
    else:
        content.append("   🎩 [yellow]Perhaps we might focus on establishing better patterns?[/]")

    if streaks["longest_abstinence"] >= 30:
        content.append("   🌟 [bold cyan]Your abstinence record demonstrates remarkable self-discipline![/]")
    elif streaks["longest_abstinence"] >= 14:
        content.append("   🌟 [cyan]Two weeks of abstinence - quite distinguished![/]")
    elif streaks["longest_abstinence"] >= 7:
        content.append("   🌟 [cyan]A full week of abstinence shows admirable restraint.[/]")

    streaks_content = "\n".join(content)
    butler_report("Achievement Record", streaks_content, "here are your distinguished achievements:")


@app.command()
def edit():
    """Open the drinks data file in your default editor for manual adjustments."""
    ensure_store()  # Make sure the CSV file exists

    address = butler_address()
    message = f"opening the ledger at {CSV_PATH} for your review..."
    console.print(f"\n{HAT}{butler_phrase(address, message)}")

    try:
        import os

        # Try to find a suitable text editor
        editor = None

        # First, check environment variables
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")

        if editor:
            # Use the explicitly set editor
            subprocess.run([editor, str(CSV_PATH)], check=True)
        elif sys.platform == "darwin":
            # macOS - try common editors in order of preference
            editors_to_try = [
                ["code", str(CSV_PATH)],  # VSCode
                ["subl", str(CSV_PATH)],  # Sublime Text
                ["atom", str(CSV_PATH)],  # Atom
                ["nano", str(CSV_PATH)],  # nano (always available)
            ]

            success = False
            for cmd in editors_to_try:
                try:
                    subprocess.run(cmd, check=True)
                    success = True
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue

            if not success:
                # Fall back to TextEdit (always available on macOS)
                subprocess.run(["open", "-a", "TextEdit", str(CSV_PATH)], check=True)

        elif sys.platform == "win32":
            # Windows - try notepad first, then system default
            try:
                subprocess.run(["notepad", str(CSV_PATH)], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                subprocess.run(["start", str(CSV_PATH)], shell=True, check=True)
        else:
            # Linux and others
            editors_to_try = [
                ["code", str(CSV_PATH)],  # VSCode
                ["gedit", str(CSV_PATH)],  # GNOME Text Editor
                ["nano", str(CSV_PATH)],  # nano
                ["vim", str(CSV_PATH)],  # vim
            ]

            success = False
            for cmd in editors_to_try:
                try:
                    subprocess.run(cmd, check=True)
                    success = True
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue

            if not success:
                subprocess.run(["xdg-open", str(CSV_PATH)], check=True)

        console.print("    [dim]The ledger has been presented for your examination.[/]")

    except subprocess.CalledProcessError as e:
        console.print(
            f"    [red]I regret to inform you that opening the ledger failed: {e}[/]"
        )
        console.print(f"    [dim]You may manually access the file at: {CSV_PATH}[/]")
        console.print(
            "    [dim]Tip: Set your preferred editor with 'export EDITOR=code' (or your preferred editor)[/]"
        )
    except FileNotFoundError:
        console.print(
            "    [red]I'm afraid no suitable application was found to open the ledger.[/]"
        )
        console.print(f"    [dim]You may manually access the file at: {CSV_PATH}[/]")
        console.print(
            "    [dim]Tip: Set your preferred editor with 'export EDITOR=code' (or your preferred editor)[/]"
        )


@app.command()
def interactive():
    """Launch the interactive Butler Console for distinguished data management."""
    try:
        from .console import run_console

        address = butler_address()
        message = "launching the distinguished interactive console..."
        console.print(f"\n{HAT}{butler_phrase(address, message)}")

        run_console()

    except ImportError as e:
        console.print(
            "    [red]I regret that the interactive console requires additional dependencies.[/]"
        )
        console.print(
            "    [dim]Please install with: pip install textual[/]"
        )
        console.print(f"    [dim]Error details: {e}[/]")
