# ticktick-stickies

[![CI](https://github.com/mpasternak/ticktick-stickies/actions/workflows/ci.yml/badge.svg)](https://github.com/mpasternak/ticktick-stickies/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Desktop **sticky notes** with your [TickTick](https://ticktick.com) tasks — **overdue**,
**today**, and the **Eisenhower matrix** quadrants (*important & urgent*,
*not important & urgent*, …) — that refresh themselves. Built for
[Übersicht](https://tracesof.net/uebersicht/) on macOS, powered by a tiny
dependency-free Python script that talks straight to the TickTick Open API.

Sister project of [freshdesk-stickies](https://github.com/mpasternak/freshdesk-stickies):
same notes, same controls, different data source.

```
┌─ Przeterminowane ──────┐  ┌─ Na dziś ──────────────┐
│ −8d 🔴 Send the offer  │  │ ⏰09:30 Call the bank   │
│ −3d 🟠 Fix the gutter  │  │ 18:00 🔵 Gym            │
│ −1d    Pay the invoice │  │ dziś 🔴 Finish the doc  │
└────────────────────────┘  └────────────────────────┘
┌─ Ważne i pilne ────────┐  ┌─ Nieważne, pilne ──────┐
│ ⏳ Po terminie          │  │ ☀️ Dziś                 │
│ −8d 🔴 Send the offer  │  │ dziś 🔵 Order filters   │
│ 📅 Później              │  │ Bez daty                │
│ 24.10 🔴 Tax return    │  │ 🔵 Tidy the garage      │
└────────────────────────┘  └────────────────────────┘
```

## How it works

- `ticktick_lib.py` — fetches undone tasks via `POST /open/v1/task/filter`,
  classifies each one as overdue / today / later / no date, and sorts it.
- `tt_list.py <view>` — CLI used both for testing (pretty text) and by the
  widget (`--json`).
- `make_widget.py "<name>" --view <view>` — stamps out a self-contained Übersicht
  widget (`widgets/ticktick-<slug>.jsx`) at a chosen screen position.

No third-party Python packages — only the standard library, so the system
`python3` on macOS is enough.

## Views

| View | Shows | Order |
|---|---|---|
| `overdue` | last day of the task is before today | priority, then oldest first |
| `today` | task falls on today (incl. multi-day tasks running today) | timed first (chronologically), then all-day by priority |
| `q1` | **important & urgent** — High priority | sections: overdue → today → later → no date |
| `q2` | important, not urgent — Medium priority | same |
| `q3` | **not important & urgent** — Low priority | same |
| `q4` | not important, not urgent — no priority | same |

Like TickTick itself, a timed task whose hour already passed today stays in
**today** (shown as `⏰09:30` in red), not in overdue.

The quadrants follow TickTick's **default** matrix rules (quadrant = priority).
The API doesn't expose custom matrix rules, so if you changed yours, mirror it
in `~/.config/ticktick/quadrants.json` (priorities: none 0, low 1, medium 3, high 5):

```json
{"q1": [5], "q3": [1, 0]}
```

Notes (`NOTE` items) are skipped. The filter endpoint returns at most 200 tasks
per call; if you hit that, the count shows `200+`.

## Setup

1. **Install Übersicht** (once):
   ```sh
   brew install --cask ubersicht
   ```
   Then launch it.

2. **Create an API token**: TickTick web app → avatar → **Settings → Account →
   API Token**, then store it (kept in `~/.config/ticktick/`, never in the repo):
   ```sh
   mkdir -p ~/.config/ticktick
   printf '%s' 'YOUR_TOKEN' > ~/.config/ticktick/token
   chmod 600 ~/.config/ticktick/token
   ```
   (Alternatively export `TICKTICK_TOKEN`. For Dida365 set
   `TICKTICK_API=https://api.dida365.com`.)

3. **Test from the terminal:**
   ```sh
   python3 tt_list.py today
   python3 tt_list.py q1
   ```

4. **Generate the notes** — the default set (overdue, today, Q1, Q3) comes from
   `notes.example.sh`:
   ```sh
   ./regen.sh
   ```
   Or one by one:
   ```sh
   python3 make_widget.py "Przeterminowane" --view overdue --limit 30 --top 40 --left 40 --accent "#e5534b"
   python3 make_widget.py "Ważne, niepilne" --view q2 --top 680 --left 40 --theme "zielony ciemny"
   ```

5. **Install the widgets** into Übersicht:
   ```sh
   ./install-widgets.sh
   ```
   then **⌘R** in Übersicht.

## The notes

Each note has the same controls as in freshdesk-stickies (none of them start a drag):

- **🎨 colour** — 6×6 palette of background themes, remembered per note;
- **⟳ refresh** — re-runs that note's query now, without waiting for the 5-minute cycle;
- **▾ / ▸ collapse** — shrinks the note to its title + counts strip;
- **✕ hide** — collapses the note to a small **📌 pin**; click the pin to bring it back.

**Drag** a note to move it; drag its **bottom edge** to set a fixed height (the list
then scrolls), **double-click** that edge to go back to auto-height. Position,
colour, collapse, hide and height are all remembered in localStorage. Clicking a
task opens it in the TickTick web app. Offline, the note keeps showing the last
data it got (marked 📴).

`--limit N` trims a long list; the note then ends with "…i jeszcze N w TickTicku"
and the header count still shows the total.

## Regenerating and installing

`make_widget.py` is the template; generated `widgets/*.jsx` are **git-ignored**
(they contain machine-specific absolute paths).

- `./regen.sh` — rebuilds every note listed in `~/.config/ticktick/notes.sh`
  (or `TICKTICK_NOTES`); without that file it uses `notes.example.sh`. To customise:
  `cp notes.example.sh ~/.config/ticktick/notes.sh`. `--top/--left` are only
  **starting** positions — once dragged, the saved position wins.
- `./install-widgets.sh` — copies `widgets/ticktick-*.jsx` into Übersicht's widgets folder.

When to run what:

- Changed the **template** or `notes.sh`: `./regen.sh && ./install-widgets.sh`, then **⌘R**.
- Changed only `ticktick_lib.py` / `tt_list.py`: just **⌘R** (or **⟳**) — the
  widget calls those scripts live.

## License

MIT — see [LICENSE](LICENSE).
