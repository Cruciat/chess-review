"""
Verifica che Stockfish sia raggiungibile e misura quanto è veloce.

Uso: python scripts/prova_motore.py [PROFONDITA]
"""

from __future__ import annotations

import sys
import time

import chess

from chessreview.engine import DEFAULT_DEPTH, Engine, find_stockfish

#: Tre posizioni di difficoltà crescente: apertura, mediogioco, finale.
POSIZIONI = [
    ("Iniziale", chess.STARTING_FEN),
    (
        "Mediogioco",
        "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P1B2/2PBPN2/PP1N1PPP/R2QK2R w KQ - 0 9",
    ),
    ("Finale di torri", "8/5pk1/6p1/7p/8/1R6/5PPP/6K1 w - - 0 1"),
]


def main() -> int:
    path = find_stockfish()
    if path is None:
        print("Stockfish non trovato.")
        print("  apt install stockfish")
        print("  oppure: export STOCKFISH_PATH=/percorso/del/binario")
        return 1

    depth = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DEPTH
    print(f"Motore: {path}")
    print(f"Profondità {depth}, tre varianti\n")

    tempi: list[float] = []

    with Engine(threads=1, hash_mb=128) as engine:
        for nome, fen in POSIZIONI:
            start = time.monotonic()
            analysis = engine.analyse_fen(fen, depth=depth, multipv=3)
            elapsed = time.monotonic() - start
            tempi.append(elapsed)

            print(f"{nome}  ({elapsed:.2f}s)")
            for line in analysis.lines:
                print(f"  {line.rank}. {line.move_san:<8} {str(line.evaluation):>8}")
            margin = analysis.margin_over_second
            if margin is not None:
                print(f"  margine sulla seconda: {margin} cp")
            print()

    media = sum(tempi) / len(tempi)
    print(f"Media per posizione: {media:.2f}s")
    print(f"Una partita da 55 semimosse: circa {media * 55:.0f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
