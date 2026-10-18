# Wzór listy karteczek dla regen.sh. Żeby go zmienić, skopiuj do
# ~/.config/ticktick/notes.sh i dopasuj (bez tego pliku regen.sh używa tego wzoru).
#
# note "Nazwa" --view overdue|today|q1|q2|q3|q4 [--limit N] [--top Y --left X] [--accent KOLOR] [--theme MOTYW]
#
# q1…q4 to ćwiartki macierzy Eisenhowera (domyślnie wg priorytetu: Q1 wysoki,
# Q2 średni, Q3 niski, Q4 brak — zmienisz w ~/.config/ticktick/quadrants.json).

note "Przeterminowane" --view overdue --limit 30 --top 40  --left 40  --accent "#e5534b"
note "Na dziś"         --view today   --top 40  --left 430 --accent "#f0b429"
note "Ważne i pilne"   --view q1      --limit 30 --top 360 --left 40  --accent "#d9480f"
note "Nieważne, pilne" --view q3      --limit 30 --top 360 --left 430 --accent "#3f7ae0"
