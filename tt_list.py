#!/usr/bin/env python3
"""CLI dla widgetu Übersicht i do testów w terminalu.

Użycie:
    python3 tt_list.py overdue           # przeterminowane (tekst, test)
    python3 tt_list.py today --json      # na dziś, JSON dla widgetu
    python3 tt_list.py q1                # ważne i pilne (macierz Eisenhowera)
    python3 tt_list.py q3 --limit 15     # nieważne, pilne — przycięte do 15
"""

import argparse
import json
import sys

import ticktick_lib as tt

PRIO_ICON = {tt.PRIO_HIGH: "🔴", tt.PRIO_MEDIUM: "🟠", tt.PRIO_LOW: "🔵"}
TIER_LABELS = {
    tt.TIER_OVERDUE: "Po terminie",
    tt.TIER_TODAY: "Dziś",
    tt.TIER_LATER: "Później",
    tt.TIER_NODATE: "Bez daty",
}


def _truncate(s: str, n: int = 58) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _text(data: dict) -> str:
    c = data["counts"]
    head = f"{c['total']}{'+' if c['truncated'] else ''} zadań"
    if data["grouped"]:
        head += f" ({c['overdue']} po terminie, {c['today']} na dziś)"
    lines = [f"TickTick — [{data['label']}]   {data['generated_at']}", head, ""]
    last_tier = object()
    for r in data["tasks"]:
        if data["grouped"] and r["tier"] != last_tier:
            last_tier = r["tier"]
            lines.append(f"— {TIER_LABELS[last_tier]} —")
        icon = PRIO_ICON.get(r["priority"], "  ")
        lines.append(f"  {icon} {r['due']:>7}  {_truncate(r['title'])}  ·{r['project']}")
    if not data["tasks"]:
        lines.append("  nic tu nie ma 🎉")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Lista zadań z TickTicka dla karteczki.")
    ap.add_argument("view", choices=list(tt.VIEWS), help="widok: overdue, today, q1…q4")
    ap.add_argument("--limit", type=int, default=None, help="przytnij listę do N")
    ap.add_argument("--json", action="store_true", help="wyjście JSON (dla widgetu Übersicht)")
    a = ap.parse_args()

    try:
        data = tt.build(a.view, limit=a.limit)
    except OSError as e:  # brak sieci / DNS / timeout / HTTP (URLError i HTTPError to OSError)
        # Krótki komunikat zamiast tracebacku — widget pokaże wtedy ostatnie zapamiętane dane.
        sys.exit(f"Brak połączenia z TickTickiem: {getattr(e, 'reason', e)}")

    if a.json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(_text(data))


if __name__ == "__main__":
    main()
