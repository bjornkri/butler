"""
Butler Console - Interactive TUI for managing drinks with distinguished flair.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)
from textual.binding import Binding

from .storage import (
    Entry,
    ensure_store,
    find_entry,
    load_entries,
    summarize_week,
    upsert_entry,
)


class WeekListItem(ListItem):
    """Custom list item for weeks with week start date."""

    def __init__(self, week_start: date, **kwargs) -> None:
        week_end = week_start + timedelta(days=6)
        label = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
        super().__init__(Label(label), **kwargs)
        self.week_start = week_start


class WeekList(ListView):
    """Left pane: List of weeks for navigation."""

    def on_mount(self) -> None:
        """Populate the week list when mounted."""
        # Load all entries to determine date range
        entries = load_entries()
        if not entries:
            return

        # Find the range of weeks with data
        earliest = min(e.day for e in entries)
        latest = max(e.day for e in entries)

        # Extend range to include current week
        today = date.today()
        earliest = min(earliest, today)
        latest = max(latest, today)

        # Generate weeks from earliest to a few weeks in the future
        current_week_start = earliest - timedelta(days=earliest.weekday())
        end_week_start = latest - timedelta(days=latest.weekday()) + timedelta(days=14)  # 2 weeks ahead

        weeks = []
        week_start = current_week_start
        current_week = today - timedelta(days=today.weekday())

        while week_start <= end_week_start:
            item = WeekListItem(week_start)
            if week_start == current_week:
                item.add_class("current-week")
            weeks.append(item)
            week_start += timedelta(days=7)

        # Add weeks to list
        for week_item in weeks:
            self.append(week_item)


class WeekDetail(DataTable):
    """Main pane: Detailed view of a specific week."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_week_start: Optional[date] = None
        self.setup_table()

    def setup_table(self) -> None:
        """Setup the table structure."""
        self.add_columns("Day", "Date", "Drinks", "Note")
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.show_cursor = True

    def get_selected_date(self) -> Optional[date]:
        """Get the date for the currently selected row."""
        if self.current_week_start is None or self.cursor_row < 0:
            return None
        return self.current_week_start + timedelta(days=self.cursor_row)

    def get_current_drinks(self, target_date: date) -> int:
        """Get current drink count for a date."""
        entries = load_entries()
        entry = find_entry(entries, target_date)
        return entry.count if entry and entry.count is not None else 0

    def cycle_drinks(self, target_date: date) -> tuple[int, str]:
        """Cycle through drink counts: 0→1→2→3→>3→0"""
        current = self.get_current_drinks(target_date)

        if current == 0:
            new_count = 1
            butler_msg = "🥂 A single libation noted."
        elif current == 1:
            new_count = 2
            butler_msg = "🍷 A modest pair recorded."
        elif current == 2:
            new_count = 3
            butler_msg = "🍾 Precisely at the limit."
        elif current == 3:
            new_count = 4
            butler_msg = "🍻 Entering spirited territory..."
        else:
            new_count = 0
            butler_msg = "✨ Returned to abstinence."

        # Update the data
        upsert_entry(target_date, new_count)
        return new_count, butler_msg

    def update_week(self, week_start: date) -> None:
        """Update the table to show data for the given week."""
        self.current_week_start = week_start
        self.clear()

        entries = load_entries()
        week_data = summarize_week(entries, week_start)

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for i, day_name in enumerate(days):
            current_date = week_start + timedelta(days=i)
            entry = week_data["days_map"].get(current_date)

            if entry and entry.count is not None:
                if entry.count == 0:
                    drinks_display = "✨ 0"
                elif entry.count <= 3:
                    drinks_display = f"🍷 {entry.count}"
                else:
                    drinks_display = f"🍻 {entry.count}"
                note = entry.note or ""
            else:
                drinks_display = "—"
                note = ""

            self.add_row(
                day_name,
                current_date.strftime("%b %d"),
                drinks_display,
                note,
                key=str(current_date)
            )

    def refresh_current_week(self) -> None:
        """Refresh the current week display after data changes."""
        if self.current_week_start:
            current_row = self.cursor_row
            self.update_week(self.current_week_start)
            if 0 <= current_row < self.row_count:
                self.move_cursor(row=current_row)


class InsightPanel(Static):
    """Right pane: Enhanced insights, stats, and butler's wisdom."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_week_start: Optional[date] = None

    def calculate_streaks(self, entries: list[Entry]) -> dict:
        """Calculate abstinence, drinking, and compliance streaks."""
        if not entries:
            return {"abstinence_streak": 0, "drinking_streak": 0, "longest_abstinence": 0, "compliance_streak": 0}

        today = date.today()
        current_abstinence = 0
        current_drinking = 0
        longest_abstinence = 0
        temp_abstinence = 0

        # Check recent days for current streak
        for i in range(30):
            check_date = today - timedelta(days=i)
            entry = find_entry(entries, check_date)

            if entry and entry.count and entry.count > 0:
                if i == 0:
                    current_drinking = 1
                elif current_drinking > 0:
                    current_drinking += 1
                else:
                    break
                current_abstinence = 0
            else:
                if current_drinking == 0:
                    current_abstinence += 1
                else:
                    break

        # Calculate longest abstinence streak
        sorted_entries = sorted(entries, key=lambda e: e.day)
        for entry in sorted_entries:
            if entry.count is None or entry.count == 0:
                temp_abstinence += 1
                longest_abstinence = max(longest_abstinence, temp_abstinence)
            else:
                temp_abstinence = 0

        # Calculate compliance streak (consecutive weeks in compliance)
        compliance_streak = 0
        current_week_start = today - timedelta(days=today.weekday())

        # Go backwards from current week checking compliance
        for i in range(52):  # Check up to 1 year back
            check_week_start = current_week_start - timedelta(days=7*i)
            week_summary = summarize_week(entries, check_week_start)

            if week_summary["recorded_days"] > 0 and week_summary["rule_ok"]:
                compliance_streak += 1
            else:
                break

        return {
            "abstinence_streak": current_abstinence,
            "drinking_streak": current_drinking,
            "longest_abstinence": longest_abstinence,
            "compliance_streak": compliance_streak
        }

    def get_weekly_insights(self, week_data: dict, week_start: date) -> str:
        """Generate week-specific insights and comparisons."""
        insights = []

        # Week-specific insights
        if week_data["drinking_days"] == 0:
            insights.append("• ✨ Complete abstinence week")
        elif week_data["drinking_days"] == 1:
            insights.append("• 🎯 Single drinking occasion - ideal restraint")

        if week_data["total_drinks"] <= 3 and week_data["drinking_days"] > 0:
            insights.append("• 🏆 Stayed within moderate consumption")

        # Weekend behavior analysis
        friday = week_start + timedelta(days=4)
        saturday = week_start + timedelta(days=5)
        sunday = week_start + timedelta(days=6)

        entries = load_entries()
        weekend_days = 0
        for day in [friday, saturday, sunday]:
            entry = find_entry(entries, day)
            if entry and entry.count and entry.count > 0:
                weekend_days += 1

        if weekend_days == 0:
            insights.append("• 🌟 Alcohol-free weekend")
        elif weekend_days <= 1:
            insights.append("• ✅ Restrained weekend conduct")

        return "\n".join(insights) if insights else "• Standard week pattern"

    def update_insights(self, week_start: date) -> None:
        """Update insights for the given week."""
        self.current_week_start = week_start

        entries = load_entries()
        week_data = summarize_week(entries, week_start)
        streaks = self.calculate_streaks(entries)

        # Build insights content
        week_end = week_start + timedelta(days=6)
        period = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"

        compliance_icon = "✅" if week_data["rule_ok"] else "⚠️"
        status = "Exemplary!" if week_data["rule_ok"] else "Needs Attention"
        days_progress = "🟢" if week_data['drinking_days'] <= 3 else "🔴"

        # Get week-specific insights
        weekly_insights = self.get_weekly_insights(week_data, week_start)

        content = f"""[bold]🎩 Week Assessment[/bold]
[dim]{period}[/dim]

📊 [bold]Statistics[/bold]
• Drinking days: {week_data['drinking_days']}/3 {days_progress}
• Total drinks: {week_data['total_drinks']}
• Recorded days: {week_data['recorded_days']}/7

{compliance_icon} [bold]Compliance: {status}[/bold]

🎯 [bold]Rule Status[/bold]
• Days limit (≤3): {'✅' if week_data['rule_days_ok'] else '❌'}
• Per-day limit (≤3): {'✅' if week_data['rule_per_day_ok'] else '❌'}
• Gap rule: {'✅' if week_data['rule_gap_ok'] else '❌'}

� [bold]Week Insights[/bold]
{weekly_insights}

📈 [bold]Overall Progress[/bold]"""

        # Add global streak information
        if streaks["compliance_streak"] > 0:
            if streaks["compliance_streak"] == 1:
                content += f"\n• 🎯 {streaks['compliance_streak']} week in compliance"
            else:
                content += f"\n• 🎯 {streaks['compliance_streak']} weeks in compliance"

        if streaks["abstinence_streak"] > 0:
            content += f"\n• Current abstinence: {streaks['abstinence_streak']} days"
        if streaks["drinking_streak"] > 1:
            content += f"\n• ⚠️  Consecutive drinking: {streaks['drinking_streak']} days"
        if streaks["longest_abstinence"] > 7:
            content += f"\n• Best abstinence streak: {streaks['longest_abstinence']} days"

        content += "\n\n💬 [bold]Butler's Wisdom[/bold]"

        # Week-specific wisdom (focus on this specific week)
        if week_data["rule_ok"]:
            if week_data["drinking_days"] == 0:
                content += "\n🌟 Magnificent abstinence! A week of true distinction."
            elif week_data["drinking_days"] <= 1:
                content += "\n🏆 Exceptional restraint this week!"
            else:
                content += "\n✅ All rules observed - well done!"
        else:
            content += "\n⚠️  Some concerns with this week's conduct..."

        # Only add compliance streak wisdom if it's significant (avoid repetition)
        if streaks["compliance_streak"] >= 12:
            content += f"\n🏅 {streaks['compliance_streak']} weeks of exemplary conduct - truly distinguished!"
        elif streaks["compliance_streak"] >= 8:
            content += f"\n🎖️  {streaks['compliance_streak']} weeks in compliance - most commendable!"

        # Current state wisdom (only if relevant and not repetitive)
        if streaks["abstinence_streak"] >= 14:
            content += f"\n🌟 {streaks['abstinence_streak']} days of distinguished abstinence!"
        elif streaks["drinking_streak"] >= 3:
            content += f"\n🔔 {streaks['drinking_streak']} consecutive drinking days requires attention"

        self.update(content)
class ButlerConsole(App):
    """Main Butler Console Application."""

    TITLE = "Butler Console 🎩 — Rule of 3"
    CSS_PATH = "console.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "edit_drinks", "Cycle Drinks", show=True),
        Binding("n", "edit_note", "Edit Note", show=True),
        Binding("escape", "cancel_edit", "Cancel", show=False),
        Binding("tab", "focus_next", "Next Panel", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.editing_note = False
        self.note_input: Optional[Input] = None

    def compose(self) -> ComposeResult:
        """Layout the application."""
        ensure_store()

        yield Header()

        with Horizontal():
            # Left pane: Week list (25% width)
            with Container(id="week-list-container"):
                yield Label("📅 [bold]Weeks[/bold]", id="week-list-title")
                yield WeekList(id="week-list")

            # Main pane: Week detail (50% width)
            with Container(id="week-detail-container"):
                yield Label("🗓️ [bold]Week Detail[/bold]", id="week-detail-title")
                yield WeekDetail(id="week-detail")

            # Right pane: Insights (25% width)
            with Container(id="insights-container"):
                yield InsightPanel(id="insights")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app when mounted."""
        week_detail = self.query_one("#week-detail", WeekDetail)
        insights = self.query_one("#insights", InsightPanel)

        # Get current week
        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())

        # Update detail and insights for current week
        week_detail.update_week(current_week_start)
        insights.update_insights(current_week_start)

        # Focus on the week detail table for interaction
        week_detail.focus()

    @on(ListView.Selected, "#week-list")
    def week_selected(self, event: ListView.Selected) -> None:
        """Handle week selection from the list."""
        week_item = event.item
        if isinstance(week_item, WeekListItem):
            week_detail = self.query_one("#week-detail", WeekDetail)
            insights = self.query_one("#insights", InsightPanel)

            week_detail.update_week(week_item.week_start)
            insights.update_insights(week_item.week_start)

    def refresh_all_panels(self) -> None:
        """Refresh all panels after data changes."""
        week_detail = self.query_one("#week-detail", WeekDetail)
        insights = self.query_one("#insights", InsightPanel)

        if week_detail.current_week_start:
            week_detail.refresh_current_week()
            insights.update_insights(week_detail.current_week_start)

    def action_edit_drinks(self) -> None:
        """Cycle through drink counts for the selected day."""
        if self.editing_note:
            return

        week_detail = self.query_one("#week-detail", WeekDetail)
        target_date = week_detail.get_selected_date()

        if target_date:
            new_count, butler_msg = week_detail.cycle_drinks(target_date)
            self.notify(f"🎩 {butler_msg}")
            self.refresh_all_panels()
        else:
            self.notify("🎩 No date selected for editing")

    def action_edit_note(self) -> None:
        """Start editing note for the selected day."""
        if self.editing_note:
            return

        week_detail = self.query_one("#week-detail", WeekDetail)
        target_date = week_detail.get_selected_date()

        if target_date:
            self.start_note_editing(target_date)

    def start_note_editing(self, target_date: date) -> None:
        """Start note editing mode."""
        self.editing_note = True

        entries = load_entries()
        entry = find_entry(entries, target_date)
        current_note = entry.note if entry else ""

        self.note_input = Input(
            value=current_note,
            placeholder="Enter note for this day...",
            id="note-input"
        )

        container = self.query_one("#week-detail-container")
        container.mount(self.note_input)
        self.note_input.focus()

        self.note_input.target_date = target_date
        self.notify(f"🎩 Editing note for {target_date.strftime('%B %d')}...")

    @on(Input.Submitted, "#note-input")
    def note_submitted(self, event: Input.Submitted) -> None:
        """Handle note input submission."""
        if hasattr(event.input, 'target_date'):
            target_date = event.input.target_date
            note_text = event.value.strip()

            entries = load_entries()
            entry = find_entry(entries, target_date)
            current_count = entry.count if entry and entry.count is not None else None

            upsert_entry(target_date, current_count, note_text if note_text else None)

            self.notify(f"🎩 Note updated for {target_date.strftime('%B %d')}")
            self.finish_note_editing()
            self.refresh_all_panels()

    def finish_note_editing(self) -> None:
        """Clean up note editing mode."""
        if self.note_input:
            self.note_input.remove()
            self.note_input = None
        self.editing_note = False

        week_detail = self.query_one("#week-detail", WeekDetail)
        week_detail.focus()

    def action_cancel_edit(self) -> None:
        """Cancel current editing."""
        if self.editing_note:
            self.notify("🎩 Note editing cancelled")
            self.finish_note_editing()


def run_console():
    """Entry point for the butler console."""
    app = ButlerConsole()
    app.run()


if __name__ == "__main__":
    run_console()
