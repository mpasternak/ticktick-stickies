"""Testy czystej logiki (daty, klasyfikacja, widoki, sortowanie) — bez sieci."""

import os
import time
from datetime import date, datetime, timezone

import pytest

import ticktick_lib as tt

# Strefa lokalna jak na Macu autora — CI biega w UTC, a „dziś" zależy od strefy.
os.environ["TZ"] = "Europe/Warsaw"
time.tzset()

# 18.10.2026, 14:00 w Warszawie (CEST, +02:00)
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 18)
NAMES = {"p1": "Praca"}


def _allday(day: str, **kw) -> dict:
    # tak TickTick zapisuje całodniowe: północ w strefie zadania, w UTC
    t = {"id": kw.pop("id", day), "title": "x", "isAllDay": True, "timeZone": "Europe/Warsaw"}
    t["startDate"] = t["dueDate"] = f"{day}T00:00:00+0200"
    t.update(kw)
    return t


def test_parse_dt_formats():
    a = tt.parse_dt("2026-10-17T22:00:00+0000")
    assert a == tt.parse_dt("2026-10-17T22:00:00.000+0000")
    assert a == tt.parse_dt("2026-10-18T00:00:00+02:00")
    assert a == tt.parse_dt("2026-10-17T22:00:00Z")
    assert tt.parse_dt(None) is None
    assert tt.parse_dt("") is None


def test_allday_stored_in_utc_lands_on_local_day():
    # „18.10 całodniowe" przychodzi z API jako 17.10 22:00 UTC — dzień ma być 18.10
    t = {"isAllDay": True, "timeZone": "Europe/Warsaw", "dueDate": "2026-10-17T22:00:00+0000"}
    assert tt.task_span(t)[:2] == (TODAY, TODAY)
    assert tt.classify(t, TODAY) == tt.TIER_TODAY


def test_classify_tiers():
    assert tt.classify(_allday("2026-10-17"), TODAY) == tt.TIER_OVERDUE
    assert tt.classify(_allday("2026-10-18"), TODAY) == tt.TIER_TODAY
    assert tt.classify(_allday("2026-10-19"), TODAY) == tt.TIER_LATER
    assert tt.classify({"id": "n", "title": "x"}, TODAY) == tt.TIER_NODATE


def test_multiday_allday_due_is_exclusive_end():
    # 16–18.10 całodniowe: dueDate = 19.10 00:00 (wyłączny koniec) → trwa dziś, nie „jutro"
    t = _allday("2026-10-16", dueDate="2026-10-19T00:00:00+0200")
    assert tt.task_span(t)[:2] == (date(2026, 10, 16), TODAY)
    assert tt.classify(t, TODAY) == tt.TIER_TODAY
    # 15–17.10 → już po terminie
    t = _allday("2026-10-15", dueDate="2026-10-18T00:00:00+0200")
    assert tt.classify(t, TODAY) == tt.TIER_OVERDUE


def test_timed_task_earlier_today_is_today_with_alarm():
    t = {"id": "t", "title": "x", "isAllDay": False, "dueDate": "2026-10-18T07:30:00+0000"}  # 9:30 PL
    assert tt.classify(t, TODAY) == tt.TIER_TODAY
    assert tt.due_label(t, TODAY, NOW) == "⏰09:30"
    later = {**t, "dueDate": "2026-10-18T16:00:00+0000"}  # 18:00 PL
    assert tt.due_label(later, TODAY, NOW) == "18:00"


def test_due_labels():
    assert tt.due_label(_allday("2026-10-15"), TODAY, NOW) == "−3d"
    assert tt.due_label(_allday("2026-10-18"), TODAY, NOW) == "dziś"
    assert tt.due_label(_allday("2026-10-19"), TODAY, NOW) == "jutro"
    assert tt.due_label(_allday("2026-10-24"), TODAY, NOW) == "24.10"
    assert tt.due_label({"id": "n"}, TODAY, NOW) == ""


def test_overdue_and_today_views_split_same_fetch():
    raw = [_allday("2026-10-10", id="old"), _allday("2026-10-18", id="now"), _allday("2026-10-20", id="fut")]
    assert [r["id"] for r in tt.build_rows("overdue", raw, NAMES, NOW)] == ["old"]
    assert [r["id"] for r in tt.build_rows("today", raw, NAMES, NOW)] == ["now"]


def test_today_sorts_timed_first_chronologically():
    raw = [
        _allday("2026-10-18", id="allday-high", priority=5),
        {"id": "t18", "title": "x", "dueDate": "2026-10-18T16:00:00+0000"},
        {"id": "t09", "title": "x", "dueDate": "2026-10-18T07:00:00+0000"},
    ]
    assert [r["id"] for r in tt.build_rows("today", raw, NAMES, NOW)] == ["t09", "t18", "allday-high"]


def test_quadrant_grouped_by_tier_then_priority_then_date():
    raw = [
        {"id": "nodate", "title": "x"},
        _allday("2026-10-25", id="later"),
        _allday("2026-10-12", id="overdue-old"),
        _allday("2026-10-16", id="overdue-new"),
        _allday("2026-10-18", id="today"),
    ]
    ids = [r["id"] for r in tt.build_rows("q1", raw, NAMES, NOW)]
    assert ids == ["overdue-old", "overdue-new", "today", "later", "nodate"]


def test_project_names_and_inbox():
    assert tt.project_name("inbox123", NAMES) == "Skrzynka"
    assert tt.project_name("p1", NAMES) == "Praca"
    assert tt.project_name("zzz", NAMES) == ""


def test_task_url_points_to_webapp():
    assert tt.task_url({"id": "abc", "projectId": "p1"}) == "https://ticktick.com/webapp/#p/p1/tasks/abc"


def test_quadrants_override(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "_CONFIG_DIR", tmp_path)
    assert tt.quadrants()["q1"] == [5]
    (tmp_path / "quadrants.json").write_text('{"q1": [5, 3], "bogus": [1]}', encoding="utf-8")
    q = tt.quadrants()
    assert q["q1"] == [5, 3]
    assert q["q3"] == [1]
    assert "bogus" not in q


def test_quadrants_broken_file_is_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "_CONFIG_DIR", tmp_path)
    (tmp_path / "quadrants.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(SystemExit):
        tt.quadrants()
