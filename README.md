# 🎩 Butler

A distinguished CLI butler for managing your libations with proper conduct.

Butler helps you maintain the **Rule of 3** with sophisticated tracking, intelligent nudges, and a touch of class.

## The Rule of 3 📜

- **No more than 3 drinking days per week**
- **No more than 3 drinks per day**  
- **Always at least one day between drinking days**

## Quick Start

```bash
pip install -e .
butler
```

## Example Interactions

**Record today's drinks:**

```bash
$ butler set 2
🎩 Your Grace, 🥂 a modest pair recorded for 2025-09-03.
```

**Check your standing:**

```bash
$ butler status
🎩 Sir/Madam, here is your current standing:
┌─ 📊 Current Standing ─────────────────────────────┐
│ 📅 Today's tally: 🥂 2 beverages                  │
│ 📰 Yesterday's record: ✨ none at all             │
│ 📊 This week so far: 1 drinking occasion          │
│                                                   │
│ 🧐 Exemplary restraint this week!                 │
└───────────────────────────────────────────────────┘
```

**Get gentle nudges:**

```bash
$ butler
╭─ 🎩 Butler • 📝 No entry for today ──────────────╮
│ 🎩 Good day! Your distinguished butler...        │
│ Available Commands:                               │
│ set <n>     Record drinks for today              │
│ status      View current standing                │
│ streaks     Review achievement records           │
╰───────────────────────────────────────────────────╯
```

## Key Features

- **🌟 Smart Streaks**: Tracks abstinence and compliance with "Yesterday Rule" timing
- **📊 Weekly/Monthly Views**: Elegant summaries with proper distinction for incomplete periods  
- **🎯 Intelligent Nudges**: Context-aware reminders that celebrate progress
- **⚖️ Rule Enforcement**: Immediate feedback when limits are exceeded
- **🏆 Achievement Tracking**: Celebrate milestones with distinguished flair

## Commands

| Command | Description |
|---------|-------------|
| `butler` | Distinguished welcome with status nudges |
| `set <n>` | Record drinks for today |
| `add <n>` | Add to today's tally |
| `status` | Current standing and week summary |
| `streaks` | Achievement records and milestones |
| `week` | Detailed weekly compliance view |
| `month` | Monthly summary by week |
| `interactive` | Launch the full TUI console |

---
*"Proper conduct, impeccable service, distinguished results."* 🎩
