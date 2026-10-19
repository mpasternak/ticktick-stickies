"""Testy generatora widgetów (komenda + podstawienia w szablonie)."""

from argparse import Namespace

import make_widget as mw


def _ns(**kw):
    base = dict(
        label="Na dziś", view="today", limit=None, top=40, left=40, accent="#3f7ae0", theme="grafit", height=None
    )
    base.update(kw)
    return Namespace(**base)


def test_command_passes_view():
    assert mw.build_command(_ns(view="q1")).endswith("tt_list.py q1 --json")


def test_limit_passthrough():
    assert "--limit 12" in mw.build_command(_ns(limit=12))


def test_slug_strips_polish_diacritics():
    assert mw.slug("Ważne i pilne") == "wazne-i-pilne"
    assert mw.slug("Nieważne, pilne") == "niewazne-pilne"
    assert mw.slug("Zaległe łąki") == "zalegle-laki"


def test_build_widget_substitutes_all_placeholders():
    src = mw.build_widget(_ns(label="Na dziś", accent="#abc123", top=11, left=22))
    for ph in ("__LABEL__", "__SLUG__", "__COMMAND__", "__TOP__", "__LEFT__", "__ACCENT__", "__THEME__", "__HEIGHT__"):
        assert ph not in src, f"nie podstawiono {ph}"
    assert "Karteczka TickTick: Na dziś" in src
    assert "4px solid #abc123" in src
    assert "{ x: 22, y: 11 }" in src


def test_build_widget_has_persistent_ui_and_position_keys():
    src = mw.build_widget(_ns(label="Ważne i pilne"))
    assert '"ttpos-wazne-i-pilne"' in src
    assert '"ttui-wazne-i-pilne"' in src
    assert '"ttlast-wazne-i-pilne"' in src


def test_build_widget_has_same_controls_as_freshdesk_notes():
    src = mw.build_widget(_ns())
    assert 'import { run } from "uebersicht"' in src
    assert "themePicker" in src and "🎨" in src  # kolor tła
    assert "refreshNow" in src and "Odśwież" in src  # odświeżanie
    assert "collapsed" in src  # zwijanie do nagłówka
    assert "hidden" in src and "📌" in src  # ukrycie -> pinezka
    assert "ns-resize" in src and "startResize" in src  # zmiana wysokości od dołu
    assert "renderTasks" in src


def test_start_height():
    assert "const DEFAULT_HEIGHT = null;" in mw.build_widget(_ns())
    assert "const DEFAULT_HEIGHT = 420;" in mw.build_widget(_ns(height=420))
