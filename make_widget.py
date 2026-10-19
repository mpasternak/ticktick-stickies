#!/usr/bin/env python3
"""Generator samodzielnych widgetów Übersicht (jeden plik = jedna karteczka).

Pierwszy argument to NAZWA karteczki (tytuł + nazwa pliku + klucz pozycji),
--view wybiera, co pokazuje: overdue, today albo ćwiartkę macierzy q1…q4.

Każda karteczka ma w nagłówku przyciski:
    🎨 kolor tła (paleta 6×6),
    ⟳  odśwież teraz (uruchamia komendę na żądanie przez `run` z Übersicht),
    ▾/▸ zwiń do nagłówka / rozwiń,
    ✕  ukryj — zostaje tylko pinezka „📌 NAZWA"; klik w nią przywraca.
Dolną krawędź listy można chwycić i zmienić wysokość (dwuklik = auto);
--height ustawia wysokość startową, zanim zmienisz ją myszą.
Stan (kolor / zwinięcie / ukrycie / wysokość) oraz pozycja są zapamiętane w
localStorage — przeżywają odświeżenie i restart.

Użycie:
    python3 make_widget.py "Przeterminowane" --view overdue --top 40 --left 40  --accent "#e5534b"
    python3 make_widget.py "Na dziś"         --view today   --top 40 --left 430
    python3 make_widget.py "Ważne i pilne"   --view q1      --top 360 --left 40
    python3 make_widget.py "Nieważne, pilne" --view q3      --top 360 --left 430

Powstaje plik widgets/ticktick-<slug>.jsx. Skopiuj go (albo cały katalog
widgets/) do katalogu widgetów Übersicht — patrz README. Po zmianie tego
generatora wszystkie istniejące karteczki przegenerujesz przez ./regen.sh.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Wykrywane automatycznie — żeby projekt był przenośny (zero zaszytych ścieżek).
PYTHON = sys.executable
PROJECT_DIR = str(Path(__file__).resolve().parent)
VIEWS = ("overdue", "today", "q1", "q2", "q3", "q4")

TEMPLATE = r"""// AUTO-GENEROWANE przez make_widget.py — edytuj generator, nie ten plik.
// Karteczka TickTick: __LABEL__

import { run } from "uebersicht";

export const refreshFrequency = 300000; // 5 min (Übersicht odświeża komendę cyklicznie)

export const command = `__COMMAND__`;

// Wrapper trzymamy w 0,0 — realną pozycję i wygląd ustawiamy na korzeniu
// (position: fixed), dzięki czemu karteczkę można przeciągać myszą.
export const className = `top: 0; left: 0;`;

const POS_KEY = "ttpos-__SLUG__"; // pozycja (przeciąganie) — jak dotychczas
const UI_KEY = "ttui-__SLUG__";   // zwinięcie / ukrycie / wysokość listy
const LAST_KEY = "ttlast-__SLUG__"; // ostatnie udane dane — pokazywane, gdy nie ma sieci
const DEFAULT_POS = { x: __LEFT__, y: __TOP__ };
const DEFAULT_HEIGHT = __HEIGHT__; // startowa wysokość listy (null = auto), aż do zmiany myszą
const MIN_BODY = 48;              // minimalna wysokość listy przy zmianie rozmiaru

// --- trwały stan UI (localStorage) -----------------------------------------
function loadUI() {
  try { return JSON.parse(localStorage.getItem(UI_KEY)) || {}; }
  catch (e) { return {}; } // brak/zepsuty wpis — startujemy z domyślnych
}
function saveUI(patch) {
  const next = { ...loadUI(), ...patch };
  try { localStorage.setItem(UI_KEY, JSON.stringify(next)); }
  catch (e) { /* tryb prywatny / brak miejsca — stan zostaje tylko w pamięci */ }
}

// --- ostatnie udane dane (fallback offline) ---------------------------------
function parseData(output) {
  try { const d = JSON.parse(output); return d && d.counts ? d : null; }
  catch (e) { return null; } // nie-JSON (np. komunikat błędu) = brak świeżych danych
}
function loadLast() {
  try { return JSON.parse(localStorage.getItem(LAST_KEY)); }
  catch (e) { return null; } // brak/zepsuty wpis — po prostu nie mamy kopii
}
function saveLast(d) {
  try { localStorage.setItem(LAST_KEY, JSON.stringify(d)); }
  catch (e) { /* brak miejsca — kopia zostaje tylko w pamięci (state.last) */ }
}
// Wynik komendy: udane dane zapamiętujemy, przy błędzie zostaje poprzednia kopia.
function withResult(prev, output, error) {
  const d = error ? null : parseData(output);
  if (d) saveLast(d);
  return { ...prev, busy: false, output, error, last: d || prev.last };
}

// --- motywy kolorystyczne (🎨 w nagłówku otwiera paletę 6×6; wybór zapamiętany)
// Rząd 1: odcienie neutralne; dalej kolumna = barwa, rząd = ton (głęboki → pastelowy).
const NEUTRALS = [
  ["czarny", "rgba(0,0,0,0.88)", "#f0f0f0"],
  ["grafit", "rgba(28,28,30,0.84)", "#ececec"],
  ["łupek", "rgba(58,64,74,0.88)", "#eef1f5"],
  ["stal", "rgba(120,126,136,0.90)", "#ffffff"],
  ["perła", "rgba(222,224,228,0.94)", "#1d1d1f"],
  ["biały", "rgba(250,250,252,0.94)", "#1d1d1f"],
];
const HUES = [
  ["czerwony", 355], ["pomarańczowy", 26], ["żółty", 50], ["zielony", 145], ["niebieski", 215], ["fioletowy", 275],
];
// [nazwa tonu, nasycenie %, jasność %, krycie, kolor tekstu]
const TONES = [
  ["głęboki", 45, 14, 0.9, "#f4f4f4"],
  ["ciemny", 40, 24, 0.9, "#f4f4f4"],
  ["średni", 42, 38, 0.92, "#ffffff"],
  ["jasny", 60, 76, 0.95, "#1d1d1f"],
  ["pastelowy", 70, 90, 0.95, "#1d1d1f"],
];
const THEMES = {};
NEUTRALS.forEach(([name, bg, fg]) => { THEMES[name] = { bg, fg }; });
TONES.forEach(([tone, s, l, a, fg]) => HUES.forEach(([hue, h]) => {
  THEMES[`${hue} ${tone}`] = { bg: `hsla(${h}, ${s}%, ${l}%, ${a})`, fg };
}));
const THEME_NAMES = Object.keys(THEMES); // kolejność = rzędy palety 6×6
// Nazwy z poprzedniej, mniejszej palety → najbliższy odpowiednik.
const THEME_ALIASES = {
  ciemny: "grafit", granat: "niebieski głęboki", niebieski: "niebieski ciemny", morski: "zielony głęboki",
  zielony: "zielony ciemny", oliwka: "żółty głęboki", "brąz": "pomarańczowy głęboki", bordo: "czerwony głęboki",
  "śliwka": "fioletowy głęboki", fiolet: "fioletowy ciemny", karteczka: "żółty pastelowy",
  "mięta": "zielony pastelowy", "błękit": "niebieski pastelowy", "róż": "czerwony pastelowy", jasny: "biały",
};
const DEFAULT_THEME = "__THEME__";
const resolveTheme = (name) => (THEMES[name] ? name : THEME_ALIASES[name]);
const themeOf = (name) => THEMES[resolveTheme(name)] || THEMES[resolveTheme(DEFAULT_THEME)] || THEMES.grafit;
// Linie/tła pomocnicze liczone z koloru tekstu — pasują do każdego motywu.
const mix = (pct) => `color-mix(in srgb, currentColor ${pct}%, transparent)`;

// Paleta 6×6 pod przyciskiem 🎨 (pozycja względem korzenia karteczki).
const pickerBox = {
  position: "absolute", top: 30, right: 10, zIndex: 10, padding: 6, borderRadius: 8,
  display: "grid", gridTemplateColumns: "repeat(6, 18px)", gap: 4,
  boxShadow: "0 6px 18px rgba(0,0,0,0.45)", border: "1px solid " + mix(20), cursor: "default",
};
function themePicker(current, onPick) {
  const cur = resolveTheme(current);
  return (
    <div style={{ ...pickerBox, background: themeOf(current).bg }} data-nodrag="1">
      {THEME_NAMES.map((name) => (
        <span key={name} title={name} data-nodrag="1" onClick={() => onPick(name)}
              style={{ width: 18, height: 18, borderRadius: 4, cursor: "pointer", background: THEMES[name].bg,
                       boxShadow: name === cur ? "0 0 0 2px " + THEMES[name].fg + ", 0 0 0 3px rgba(0,0,0,0.5)"
                                              : "inset 0 0 0 1px rgba(127,127,127,0.5)" }} />
      ))}
    </div>
  );
}

// --- stan widgetu (model Übersicht: initialState + updateState) -------------
const _ui = loadUI();
export const initialState = {
  output: "",
  error: null,
  busy: false,
  last: loadLast(),
  collapsed: !!_ui.collapsed,
  hidden: !!_ui.hidden,
  // "height" w zapisie (też null po dwukliku = auto) wygrywa z wartością startową
  height: "height" in _ui ? _ui.height : DEFAULT_HEIGHT,
  theme: resolveTheme(_ui.theme) || DEFAULT_THEME,
};

export const updateState = (event, prev) => {
  switch (event.type) {
    case "TT/SET":       return { ...prev, ...event.patch };
    case "TT/BUSY":      return { ...prev, busy: true };
    case "TT/REFRESHED": return withResult(prev, event.output, null);
    case "TT/ERROR":     return withResult(prev, "", event.error);
    default:
      // Wbudowane zdarzenie po zakończeniu `command` niesie output/error
      // (jego typ bywa "UB/COMMAND_RAN" — rozpoznajemy je po obecności pól).
      if ("output" in event || "error" in event) {
        return withResult(prev, event.output, event.error);
      }
      return prev;
  }
};

// --- akcje ------------------------------------------------------------------
function setUI(dispatch, patch) {
  saveUI(patch);
  dispatch({ type: "TT/SET", patch });
}
function refreshNow(dispatch) {
  dispatch({ type: "TT/BUSY" });
  run(command)
    .then((output) => dispatch({ type: "TT/REFRESHED", output }))
    .catch((err) => dispatch({ type: "TT/ERROR", error: String(err) }));
}

// --- przeciąganie pozycji (+ wykrycie „tapnięcia" do przywrócenia pinezki) --
function initDrag(el, onTap) {
  if (!el) return;
  if (onTap !== undefined) el.__ttTap = onTap; // tap = klik bez przeciągnięcia
  if (el.__ttInit) return;
  el.__ttInit = true;
  let pos;
  try { pos = JSON.parse(localStorage.getItem(POS_KEY)); } catch (e) { pos = null; }
  if (!pos) pos = { ...DEFAULT_POS };
  const apply = () => { el.style.left = pos.x + "px"; el.style.top = pos.y + "px"; };
  apply();
  let drag = false, sx = 0, sy = 0, ox = 0, oy = 0;
  el.addEventListener("mousedown", (e) => {
    if (e.target.closest("a")) return;             // klik w link działa normalnie
    if (e.target.closest("[data-nodrag]")) return; // przyciski / uchwyt nie przeciągają
    drag = true; el.__ttMoved = false;
    sx = e.clientX; sy = e.clientY; ox = pos.x; oy = pos.y;
    el.style.cursor = "grabbing";
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    pos.x = ox + (e.clientX - sx);
    pos.y = oy + (e.clientY - sy);
    if (Math.abs(e.clientX - sx) + Math.abs(e.clientY - sy) > 4) el.__ttMoved = true;
    apply();
  });
  window.addEventListener("mouseup", () => {
    if (!drag) return;
    drag = false;
    el.style.cursor = "grab";
    localStorage.setItem(POS_KEY, JSON.stringify(pos));
    if (!el.__ttMoved && el.__ttTap) el.__ttTap(); // tapnięcie bez ruchu = akcja
  });
}

// --- zmiana wysokości listy od dołu ----------------------------------------
let bodyEl = null;
const bodyRef = (el) => { if (el) bodyEl = el; };
function startResize(e, dispatch) {
  e.preventDefault();
  // Korzeń karteczki (rodzic uchwytu). Pozycję (top/left) trzymamy ZABLOKOWANĄ
  // na czas całego gestu — dzięki temu zmiana wysokości listy NIE przesuwa
  // karteczki w górę/dół (rośnie tylko dół, lewy-górny róg stoi w miejscu).
  const root = e.currentTarget ? e.currentTarget.parentElement : null;
  const lockTop = root ? root.style.top : "";
  const lockLeft = root ? root.style.left : "";
  const pin = () => {
    if (!root) return;
    if (lockTop) root.style.top = lockTop;
    if (lockLeft) root.style.left = lockLeft;
  };
  const startY = e.clientY;
  const startH = bodyEl ? bodyEl.offsetHeight : 0;
  let lastH = startH, moved = false;
  if (bodyEl) bodyEl.style.overflowY = "auto";
  const move = (ev) => {
    moved = true;
    lastH = Math.max(MIN_BODY, startH + (ev.clientY - startY));
    if (bodyEl) bodyEl.style.maxHeight = lastH + "px";
    pin(); // utrzymaj pozycję — zmieniamy wyłącznie wysokość
  };
  const up = () => {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    pin();
    if (moved) setUI(dispatch, { height: lastH }); // czysty klik nie zmienia rozmiaru
  };
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
}

// --- style ------------------------------------------------------------------
const rootStyle = {
  position: "fixed", width: "360px", pointerEvents: "auto", cursor: "grab",
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  border: "1px solid " + mix(12), borderRadius: "10px",
  boxShadow: "0 8px 24px rgba(0,0,0,0.35)", padding: "12px 14px",
  fontSize: "12px", lineHeight: 1.45,
};
const pinStyle = {
  position: "fixed", pointerEvents: "auto", cursor: "grab",
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  border: "1px solid " + mix(12), borderRadius: "8px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.28)", padding: "5px 10px",
  fontSize: "12px", fontWeight: 700, whiteSpace: "nowrap", userSelect: "none",
};
const hdr = { borderLeft: "4px solid __ACCENT__", paddingLeft: 8, marginBottom: 8 };
const hdrRow = { display: "flex", alignItems: "center", gap: 8 };
const title = {
  fontWeight: 700, fontSize: 14, letterSpacing: 0.3,
  flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
};
const sub = { fontSize: 11, opacity: 0.7 };
const ctlWrap = { display: "flex", alignItems: "center", gap: 9, flex: "0 0 auto" };
const ctl = { cursor: "pointer", opacity: 0.6, fontSize: 16, lineHeight: 1, userSelect: "none" };
const row = {
  display: "block", textDecoration: "none", color: "inherit",
  padding: "2px 0", borderTop: "1px solid " + mix(8), whiteSpace: "nowrap",
  overflow: "hidden", textOverflow: "ellipsis",
};
const idc = { fontVariantNumeric: "tabular-nums", opacity: 0.55, marginRight: 6 };
const grpHdr = { fontSize: 10, fontWeight: 700, opacity: 0.5, letterSpacing: 0.4, margin: "8px 0 1px" };
// Uchwyt zmiany wysokości: niewidoczny pas przy dolnej krawędzi (wchodzi w dolny
// padding karteczki); widać go tylko po najechaniu, kursor ↕ podpowiada chwyt.
const handle = { height: 8, margin: "2px 0 -10px", borderRadius: 4, cursor: "ns-resize", background: "transparent" };
const HANDLE_HOVER = mix(10);

const trunc = (s, n = 42) => (s.length <= n ? s : s.slice(0, n - 1) + "…");
// Z tracebacku/komunikatu zostaw ostatnią niepustą linię (sedno błędu).
const errLine = (err) => trunc(String(err).trim().split("\n").filter(Boolean).pop() || "?", 60);

const TIER_LABELS = ["⏳ Po terminie", "☀️ Dziś", "📅 Później", "Bez daty"];
const PRIO_ICON = { 5: "🔴", 3: "🟠", 1: "🔵" };
// termin po czasie (po terminie / dzisiejsza godzina minęła) — na czerwono
const late = (r) => r.tier === 0 || r.due.startsWith("⏰");
const dueStyle = (r) => ({ ...idc, color: late(r) ? "#e5534b" : undefined, opacity: late(r) ? 0.9 : 0.55 });

function taskRow(r) {
  return (
    <a style={row} href={r.url} title={`${r.title}${r.project ? " · " + r.project : ""}`} key={r.id}>
      {r.due && <span style={dueStyle(r)}>{r.due}</span>}
      {PRIO_ICON[r.priority] ? PRIO_ICON[r.priority] + " " : ""}{r.repeat ? "🔁 " : ""}{trunc(r.title)}
      {r.project && <span style={{ opacity: 0.45 }}> · {trunc(r.project, 16)}</span>}
    </a>
  );
}

// Ćwiartki: w sekcjach terminu (gdy grouped) z nagłówkiem przy zmianie tier,
// widoki „przeterminowane" / „na dziś" — płasko.
function renderTasks(rows, grouped) {
  if (!grouped) return rows.map(taskRow);
  const out = [];
  let last = null;
  rows.forEach((r) => {
    if (r.tier !== last) {
      last = r.tier;
      out.push(<div style={grpHdr} key={"h" + r.tier}>{TIER_LABELS[r.tier] || "—"}</div>);
    }
    out.push(taskRow(r));
  });
  return out;
}

// --- render -----------------------------------------------------------------
export const render = (state, dispatch) => {
  const { output, error, busy, collapsed, hidden, height, last, theme, picker } = state;
  const T = themeOf(theme);
  const paint = { background: T.bg, color: T.fg };

  // Ukryta: tylko pinezka. Klik (bez przeciągnięcia) przywraca; nadal przeciągalna.
  if (hidden) {
    return (
      <div style={{ ...pinStyle, ...paint }} ref={(el) => initDrag(el, () => setUI(dispatch, { hidden: false }))}>
        📌 __LABEL__
      </div>
    );
  }

  // Świeże dane, a gdy ich brak (np. offline) — ostatnia zapamiętana kopia.
  const fresh = error ? null : parseData(output);
  const failed = !!error || (output !== "" && !fresh); // "" = komenda jeszcze nie wróciła
  const errText = error || (failed ? output : null);
  const d = fresh || last;
  const stale = !fresh && !!d && failed;
  const c = d && d.counts;

  const controls = (
    <span style={ctlWrap}>
      <span style={{ ...ctl, fontSize: 13 }} data-nodrag="1" title={`Kolor: ${theme}`}
            onClick={() => dispatch({ type: "TT/SET", patch: { picker: !picker } })}>🎨</span>
      <span style={ctl} data-nodrag="1" title="Odśwież teraz"
            onClick={() => refreshNow(dispatch)}>{busy ? "⏳" : "⟳"}</span>
      <span style={ctl} data-nodrag="1" title={collapsed ? "Rozwiń" : "Zwiń"}
            onClick={() => setUI(dispatch, { collapsed: !collapsed })}>{collapsed ? "▸" : "▾"}</span>
      <span style={ctl} data-nodrag="1" title="Ukryj (zostanie pinezka)"
            onClick={() => setUI(dispatch, { hidden: true })}>✕</span>
    </span>
  );

  const countsLine = c
    ? <span>
        {stale ? "📴 " : ""}{c.total}{c.truncated ? "+" : ""} zadań
        {d.grouped && c.overdue > 0 ? ` · ⏳ ${c.overdue} po terminie` : ""}
        {d.grouped && c.today > 0 ? ` · ☀️ ${c.today} dziś` : ""}
      </span>
    : <span>{errText ? "⚠️ błąd" : "—"}</span>;

  // Zwinięta: tylko pasek nagłówka (tytuł + liczniki + przyciski).
  if (collapsed) {
    return (
      <div style={{ ...rootStyle, ...paint, padding: "8px 14px" }} ref={(el) => initDrag(el, null)}>
        {picker && themePicker(theme, (name) => setUI(dispatch, { theme: name, picker: false }))}
        <div style={{ ...hdr, marginBottom: 0, ...hdrRow }}>
          <span style={title}>__LABEL__</span>
          <span style={{ ...sub, flex: "0 0 auto" }}>{countsLine}</span>
          {controls}
        </div>
      </div>
    );
  }

  // Pełna karteczka.
  return (
    <div style={{ ...rootStyle, ...paint }} ref={(el) => initDrag(el, null)}>
        {picker && themePicker(theme, (name) => setUI(dispatch, { theme: name, picker: false }))}
      <div style={hdr}>
        <div style={hdrRow}>
          <div style={title}>__LABEL__</div>
          {controls}
        </div>
        <div style={sub}>{countsLine}</div>
      </div>

      <div ref={bodyRef}
           style={{ maxHeight: height ? height + "px" : "none",
                    overflowY: height ? "auto" : "visible" }}>
        {stale && (
          <div style={{ ...sub, marginBottom: 4 }} title={String(errText)}>
            📴 brak połączenia — dane z {d.generated_at ? d.generated_at.slice(0, 16).replace("T", " ") : "?"}
          </div>
        )}
        {!d && errText && <div style={sub} title={String(errText)}>⚠️ błąd: {errLine(errText)}</div>}
        {!d && !errText && (
          <div style={sub}>Brak danych — sprawdź token API (~/.config/ticktick/token).</div>
        )}
        {d && d.tasks && d.tasks.length === 0 && (
          <div style={sub}>nic tu nie ma 🎉</div>
        )}
        {d && d.tasks && renderTasks(d.tasks, d.grouped)}
        {d && d.tasks && c.total > d.tasks.length && (
          <div style={{ ...sub, marginTop: 4 }}>…i jeszcze {c.total - d.tasks.length} w TickTicku</div>
        )}
        {d && d.generated_at && (
          <div style={{ ...sub, marginTop: 8, textAlign: "right" }}>{d.generated_at.slice(11, 16)}</div>
        )}
      </div>

      <div style={handle} data-nodrag="1"
           onMouseEnter={(e) => { e.currentTarget.style.background = HANDLE_HOVER; }}
           onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
           title="Przeciągnij = zmień wysokość · dwuklik = auto"
           onMouseDown={(e) => startResize(e, dispatch)}
           onDoubleClick={() => {
             setUI(dispatch, { height: null });
             if (bodyEl) { bodyEl.style.maxHeight = "none"; bodyEl.style.overflowY = "visible"; }
           }} />
    </div>
  );
};
"""


def slug(label: str) -> str:
    # „Ważne i pilne" → „wazne-i-pilne" (ł nie ma rozkładu NFKD — zamieniamy ręcznie)
    ascii_ = unicodedata.normalize("NFKD", label.replace("ł", "l").replace("Ł", "L"))
    ascii_ = ascii_.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def build_command(a) -> str:
    """Złóż komendę tt_list dla widgetu z opcji generatora."""
    tt_args = [a.view]
    if a.limit is not None:
        tt_args += ["--limit", str(a.limit)]
    tt_args.append("--json")
    return f"cd {PROJECT_DIR} && {PYTHON} tt_list.py " + " ".join(tt_args)


def build_widget(a) -> str:
    """Wyrenderuj treść pliku .jsx karteczki z opcji generatora."""
    return (
        TEMPLATE.replace("__COMMAND__", build_command(a))
        .replace("__SLUG__", slug(a.label))
        .replace("__LABEL__", a.label)
        .replace("__TOP__", str(a.top))
        .replace("__LEFT__", str(a.left))
        .replace("__ACCENT__", a.accent)
        .replace("__THEME__", a.theme)
        .replace("__HEIGHT__", str(a.height) if a.height else "null")
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Generator karteczek Übersicht dla TickTicka.")
    ap.add_argument("label", help="nazwa karteczki: tytuł + nazwa pliku + klucz pozycji")
    ap.add_argument("--view", required=True, choices=VIEWS, help="overdue, today albo ćwiartka q1…q4")
    ap.add_argument("--limit", type=int, default=None, help="przytnij listę do N")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--left", type=int, default=40)
    ap.add_argument(
        "--height", type=int, default=None, help="startowa wysokość listy w px (ze scrollem); domyślnie auto"
    )
    ap.add_argument("--accent", default="#3f7ae0")
    ap.add_argument(
        "--theme",
        default="grafit",
        help="kolor startowy: grafit, biały… albo '<barwa> <ton>', np. 'zielony ciemny' (potem 🎨)",
    )
    a = ap.parse_args()

    content = build_widget(a)
    out = Path(__file__).parent / "widgets" / f"ticktick-{slug(a.label)}.jsx"
    out.write_text(content, encoding="utf-8")
    print(f"zapisano {out}")


if __name__ == "__main__":
    main()
