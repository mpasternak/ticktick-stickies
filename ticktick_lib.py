"""Rdzeń logiki sticky-notes z TickTicka: pobranie, klasyfikacja terminów, widoki.

Czysty stdlib (urllib) — żeby działało na każdym python3 na macOS bez pip.

Konfiguracja (nic wrażliwego nie jest zaszyte w kodzie):
- token: zmienna TICKTICK_TOKEN albo plik ~/.config/ticktick/token
  (TickTick web → avatar → Settings → Account → API Token)
- serwer API: zmienna TICKTICK_API (domyślnie https://api.ticktick.com;
  dla Dida365: https://api.dida365.com)
- ćwiartki macierzy: opcjonalny ~/.config/ticktick/quadrants.json, np.
  {"q1": [5], "q3": [1]} — nadpisuje domyślne mapowanie priorytetów
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # py<3.9 — wtedy całodniowe liczymy w strefie lokalnej
    ZoneInfo = None
    ZoneInfoNotFoundError = KeyError

_CONFIG_DIR = Path.home() / ".config" / "ticktick"
_CACHE_DIR = Path.home() / ".cache" / "ticktick"
_PROJECTS_CACHE = _CACHE_DIR / "projects.json"
PROJECTS_TTL = 6 * 3600  # nazwy list zmieniają się rzadko — odświeżamy co 6 h

FILTER_MAX = 200  # /task/filter zwraca najwyżej tyle zadań

# Priorytety TickTicka: None 0, Low 1, Medium 3, High 5.
PRIO_NONE, PRIO_LOW, PRIO_MEDIUM, PRIO_HIGH = 0, 1, 3, 5

# Domyślne reguły macierzy Eisenhowera w TickTicku (ćwiartka = priorytet).
DEFAULT_QUADRANTS = {
    "q1": [PRIO_HIGH],  # ważne i pilne
    "q2": [PRIO_MEDIUM],  # ważne, niepilne
    "q3": [PRIO_LOW],  # nieważne, pilne
    "q4": [PRIO_NONE],  # nieważne, niepilne
}

VIEWS = {
    "overdue": "Przeterminowane",
    "today": "Na dziś",
    "q1": "Ważne i pilne",
    "q2": "Ważne, niepilne",
    "q3": "Nieważne, pilne",
    "q4": "Nieważne, niepilne",
}

# Sekcje w karteczkach ćwiartek (0 = najpilniejsza).
TIER_OVERDUE, TIER_TODAY, TIER_LATER, TIER_NODATE = 0, 1, 2, 3


# ── Konfiguracja / HTTP ──────────────────────────────────────────────────────


def _token() -> str:
    val = os.environ.get("TICKTICK_TOKEN")
    if val:
        return val.strip()
    path = _CONFIG_DIR / "token"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    raise SystemExit(f"Brak tokenu API. Ustaw TICKTICK_TOKEN albo wpisz do {path} (TickTick → Settings → API Token).")


def _api_base() -> str:
    return os.environ.get("TICKTICK_API", "https://api.ticktick.com").rstrip("/")


def _request(method: str, path: str, body: dict | None = None) -> dict | list:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{_api_base()}/open/v1/{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else []


def quadrants() -> dict[str, list[int]]:
    """Mapowanie ćwiartka → priorytety; plik quadrants.json nadpisuje domyślne."""
    q = {k: list(v) for k, v in DEFAULT_QUADRANTS.items()}
    path = _CONFIG_DIR / "quadrants.json"
    if path.exists():
        try:
            override = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"Zepsuty {path}: {e}") from e
        for k, v in override.items():
            if k in q:
                q[k] = [int(p) for p in v]
    return q


def task_url(t: dict) -> str:
    pid = urllib.parse.quote(t.get("projectId") or "inbox")
    return f"https://ticktick.com/webapp/#p/{pid}/tasks/{urllib.parse.quote(t['id'])}"


# ── Listy (nazwy projektów, z cache na dysku) ────────────────────────────────


def _project_names() -> dict[str, str]:
    """id listy → nazwa. Cache na PROJECTS_TTL; błąd sieci = ostatnia kopia."""
    cached: dict = {}
    if _PROJECTS_CACHE.exists():
        try:
            cached = json.loads(_PROJECTS_CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}  # zepsuty cache — po prostu pobierzemy od nowa
        fresh = datetime.now().timestamp() - cached.get("ts", 0) < PROJECTS_TTL
        if fresh and cached.get("names"):
            return cached["names"]
    try:
        projects = _request("GET", "project")
    except OSError as e:  # nazwy list to ozdobnik — bez nich karteczka i tak działa
        print(f"ticktick: nie pobrano list: {e}", file=sys.stderr)
        return cached.get("names", {})
    names = {p["id"]: p.get("name") or "" for p in projects if isinstance(p, dict) and p.get("id")}
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _PROJECTS_CACHE.write_text(
        json.dumps({"ts": datetime.now().timestamp(), "names": names}, ensure_ascii=False), encoding="utf-8"
    )
    return names


def project_name(pid: str | None, names: dict[str, str]) -> str:
    if not pid or pid.startswith("inbox"):
        return "Skrzynka"
    return names.get(pid, "")


# ── Daty ─────────────────────────────────────────────────────────────────────


def parse_dt(s: str | None) -> datetime | None:
    """TickTick: '2026-10-18T00:00:00+0000' albo z milisekundami '…00.000+0000'."""
    if not s:
        return None
    s = s.replace("Z", "+0000")
    if "." in s:  # ucinamy ułamek sekund — strptime z py3.9 i tak go nie potrzebuje
        head, _, tail = s.partition(".")
        tz = tail[next((i for i, ch in enumerate(tail) if ch in "+-"), len(tail)) :]
        s = head + tz
    if len(s) > 6 and s[-6] in "+-" and s[-3] == ":":  # '+02:00' → '+0200'
        s = s[:-3] + s[-2:]
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def _tz(name: str | None):
    if not name or ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None  # nieznana strefa w zadaniu — liczymy w strefie lokalnej


def _local_day(dt: datetime, tzname: str | None) -> date:
    """Dzień kalendarzowy terminu: całodniowe w strefie zadania, reszta lokalnie."""
    tz = _tz(tzname)
    return (dt.astimezone(tz) if tz else dt.astimezone()).date()


def task_span(t: dict) -> tuple[date, date, datetime | None] | None:
    """(pierwszy dzień, ostatni dzień, godzina terminu albo None dla całodniowych).

    None = zadanie bez daty. Całodniowe wielodniowe mają w TickTicku dueDate
    jako WYŁĄCZNY koniec (północ dnia po ostatnim), stąd -1 dzień.
    """
    start = parse_dt(t.get("startDate"))
    due = parse_dt(t.get("dueDate")) or start
    if due is None:
        return None
    start = start or due
    if t.get("isAllDay"):
        first = _local_day(start, t.get("timeZone"))
        last = _local_day(due, t.get("timeZone"))
        if due > start:
            last -= timedelta(days=1)
        return first, max(first, last), None
    return _local_day(start, None), _local_day(due, None), due


def classify(t: dict, today: date) -> int:
    """Sekcja zadania względem dziś: po terminie / dziś / później / bez daty.

    Jak w TickTicku: „przeterminowane" to ostatni dzień PRZED dziś; zadanie
    z godziną, która dziś już minęła, jest nadal „na dziś" (z flagą ⏰).
    """
    span = task_span(t)
    if span is None:
        return TIER_NODATE
    first, last, _ = span
    if last < today:
        return TIER_OVERDUE
    if first <= today:
        return TIER_TODAY
    return TIER_LATER


def due_label(t: dict, today: date, now: datetime) -> str:
    span = task_span(t)
    if span is None:
        return ""
    first, last, at = span
    if last < today:
        return f"−{(today - last).days}d"
    if first <= today:
        if at is not None and last == today:
            hhmm = at.astimezone().strftime("%H:%M")
            return f"⏰{hhmm}" if at < now else hhmm
        return "dziś"
    if first == today + timedelta(days=1):
        return "jutro"
    return first.strftime("%d.%m")


# ── Pobranie ─────────────────────────────────────────────────────────────────


def _filter(body: dict) -> list[dict]:
    res = _request("POST", "task/filter", {"status": [0], **body})
    # notatki (kind NOTE) to nie zadania — nie mają czego „zrobić"
    return [t for t in res if isinstance(t, dict) and t.get("kind") != "NOTE"] if isinstance(res, list) else []


def _end_of_today_utc(today: date) -> str:
    end = datetime.combine(today, time(23, 59, 59)).astimezone(timezone.utc)
    return end.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def fetch(view: str, today: date) -> tuple[list[dict], bool]:
    """Surowe zadania dla widoku + czy trafiliśmy w limit FILTER_MAX."""
    if view in ("overdue", "today"):
        # filtr API: startDate ≤ koniec dziś — łapie i przeterminowane, i dzisiejsze
        # (też wielodniowe, które trwają dziś); resztę rozstrzyga classify()
        raw = _filter({"endDate": _end_of_today_utc(today)})
    elif view in DEFAULT_QUADRANTS:
        raw = _filter({"priority": quadrants()[view]})
    else:
        raise SystemExit(f"Nieznany widok {view!r}. Dostępne: {', '.join(VIEWS)}")
    return raw, len(raw) >= FILTER_MAX


# ── Publiczne API ────────────────────────────────────────────────────────────


def _sort_key(r: dict) -> tuple:
    # w sekcji: wyższy priorytet wyżej, potem wcześniejszy termin, potem kolejność z TickTicka
    return (r["tier"], -r["priority"], r["sort_day"] or "9999", r["sort_order"])


def build_rows(view: str, raw: list[dict], names: dict[str, str], now: datetime) -> list[dict]:
    """Czysta część build(): klasyfikacja, filtr widoku i sortowanie (bez sieci)."""
    today = now.astimezone().date()
    rows = []
    for t in raw:
        tier = classify(t, today)
        if view == "overdue" and tier != TIER_OVERDUE:
            continue
        if view == "today" and tier != TIER_TODAY:
            continue
        span = task_span(t)
        rows.append(
            {
                "id": t["id"],
                "url": task_url(t),
                "title": (t.get("title") or "").strip() or "(bez tytułu)",
                "priority": t.get("priority") or 0,
                "project": project_name(t.get("projectId"), names),
                "tags": t.get("tags") or [],
                "tier": tier,
                "due": due_label(t, today, now),
                "sort_day": span[1].isoformat() if span else None,
                "sort_at": span[2].isoformat() if span and span[2] else None,
                "sort_order": t.get("sortOrder") or 0,
                "repeat": bool(t.get("repeatFlag")),
            }
        )
    if view == "today":
        # dziś: najpierw z godziną (chronologicznie), potem całodniowe wg priorytetu
        rows.sort(key=lambda r: (r["sort_at"] is None, r["sort_at"] or "", -r["priority"], r["sort_order"]))
    else:
        rows.sort(key=_sort_key)
    return rows


def build(view: str, limit: int | None = None) -> dict:
    """Zbuduj listę zadań dla karteczki danego widoku (overdue/today/q1…q4)."""
    now = datetime.now(timezone.utc)
    today = now.astimezone().date()
    raw, truncated = fetch(view, today)
    rows = build_rows(view, raw, _project_names(), now)
    counts = {
        "total": len(rows),
        "overdue": sum(1 for r in rows if r["tier"] == TIER_OVERDUE),
        "today": sum(1 for r in rows if r["tier"] == TIER_TODAY),
        "truncated": truncated,
    }
    if limit:
        rows = rows[:limit]
    return {
        "view": view,
        "label": VIEWS[view],
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "grouped": view in DEFAULT_QUADRANTS,  # ćwiartki w sekcjach terminu
        "tasks": rows,
        "counts": counts,
    }
