#!/usr/bin/env bash
# Przegenerowuje WSZYSTKIE karteczki z aktualnego szablonu make_widget.py.
#
# Lista karteczek (nazwy, widoki, pozycje) leży w ~/.config/ticktick/notes.sh
# (albo pliku wskazanym przez TICKTICK_NOTES). Gdy go nie ma, używamy wzoru
# z repo — notes.example.sh (cztery karteczki: przeterminowane, dziś, Q1, Q3).
# W pliku wołasz `note "Nazwa" --view WIDOK [opcje make_widget.py]`.
#
# --top/--left to tylko pozycje STARTOWE: po pierwszym przeciągnięciu myszą
# zapamiętana pozycja (localStorage, klucz ttpos-<slug>) ma pierwszeństwo, więc
# regeneracja nie przesuwa już raz ustawionych karteczek.
#
# Po regeneracji wgraj zmiany do Übersicht: ./install-widgets.sh
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
NOTES="${TICKTICK_NOTES:-$HOME/.config/ticktick/notes.sh}"

if [ ! -f "$NOTES" ]; then
  echo "Brak $NOTES — używam wzoru notes.example.sh."
  NOTES="notes.example.sh"
fi

note() { "$PY" make_widget.py "$@"; }

# shellcheck source=notes.example.sh
source "$NOTES"

echo "Przegenerowano wszystkie karteczki. Wgraj do Übersicht: ./install-widgets.sh"
