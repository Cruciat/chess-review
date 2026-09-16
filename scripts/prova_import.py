"""
Prova manuale contro l'API vera.
Uso: python scripts/prova_import.py TUO_USERNAME [ANNO MESE]
"""

from __future__ import annotations

import sys
from collections import Counter

from chessreview.chesscom import ChessComClient


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/prova_import.py USERNAME [ANNO MESE]")
        return 1

    username = sys.argv[1]

    with ChessComClient(f"chessreview/0.1 ({username})") as client:
        archives = client.list_archives(username)
        if not archives:
            print("Nessun archivio: il giocatore non ha partite pubbliche.")
            return 1

        print(f"{len(archives)} mesi, dal {archives[0]} al {archives[-1]}\n")

        if len(sys.argv) >= 4:
            games = client.fetch_month(username, int(sys.argv[2]), int(sys.argv[3]))
            label = f"{sys.argv[2]}-{int(sys.argv[3]):02d}"
        else:
            games = client.fetch_archive(archives[-1], username)
            label = str(archives[-1])

        print(f"{len(games)} partite in {label}\n")
        if not games:
            return 0

        print(f"Tipi di gioco: {dict(Counter(g.rules for g in games))}")
        print(f"Controlli di tempo: {dict(Counter(g.time_class for g in games))}")

        openings = Counter(g.eco_code for g in games if g.eco_code)
        print(f"Aperture più frequenti: {openings.most_common(5)}\n")

        print("Ultime partite:")
        for game in games[-5:]:
            outcome = game.outcome_for(username)
            clock = game.clock
            print(
                f"  {game.started_at.date()}  {game.time_class:<8} "
                f"{outcome.value if outcome else '?':<5} "
                f"{game.eco_code or '---':<4} "
                f"{f'{clock[0]}+{clock[1]}' if clock else '---':<8} "
                f"{(game.opening_name or '')[:40]}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
