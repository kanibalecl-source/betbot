# Append-only History

Ten modu? zapisuje histori? jako dopisywane rekordy w `data/history/*.jsonl` i `data/history/*.csv`.

Zasady:

- nigdy nie kasuje istniej?cej historii,
- nigdy nie nadpisuje ca?ego pliku historii,
- b??dy zapisu historii nie zatrzymuj? bota,
- snapshoty typu `auto_all_picks.csv` mog? si? zmienia?, ale pe?na historia ro?nie w `data/history`.
