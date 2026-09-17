"""
Analizza una partita e stampa la review a terminale.

Uso:
  python scripts/analizza.py USERNAME              ultima partita giocata
  python scripts/analizza.py USERNAME 3            la terzultima
  python scripts/analizza.py --pgn partita.pgn     da file
"""

from __future__ import annotations

import sys
import time

from chessreview.analysis import (
    DEEP_DEPTH,
    SCAN_DEPTH,
    GameAnalysis,
    MoveAnalysis,
    Phase,
    analyse_game,
)
from chessreview.chesscom import ChessComClient
from chessreview.classification import LABELS, MoveClass
from chessreview.engine import Engine, find_stockfish
from chessreview.models import Color, ImportedGame
from chessreview.positions import parse_pgn

THREADS = 4

#: Simboli in ASCII: leggibili in qualunque terminale.
GLYPHS: dict[MoveClass, str] = {
    MoveClass.BRILLIANT: "!!",
    MoveClass.CRITICAL: "! ",
    MoveClass.BEST: "* ",
    MoveClass.EXCELLENT: "  ",
    MoveClass.GOOD: "  ",
    MoveClass.INACCURACY: "?!",
    MoveClass.MISTAKE: "? ",
    MoveClass.BLUNDER: "??",
    MoveClass.MISSED_WIN: "×?",
    MoveClass.BOOK: "· ",
    MoveClass.FORCED: "= ",
}

#: Ordine in cui mostrare il riepilogo.
SUMMARY_ORDER = [
    MoveClass.BRILLIANT,
    MoveClass.CRITICAL,
    MoveClass.BEST,
    MoveClass.EXCELLENT,
    MoveClass.GOOD,
    MoveClass.INACCURACY,
    MoveClass.MISTAKE,
    MoveClass.BLUNDER,
    MoveClass.MISSED_WIN,
    MoveClass.FORCED,
]


def fetch_game(username: str, index: int) -> ImportedGame:
    """La partita numero `index` dal fondo: 1 è l'ultima giocata."""
    with ChessComClient(f"chessreview/0.1 ({username})") as client:
        archives = client.list_archives(username)
        collected: list[ImportedGame] = []

        for archive in reversed(archives):
            collected = client.fetch_archive(archive, username) + collected
            if len(collected) >= index:
                break

        if len(collected) < index:
            raise SystemExit(f"Solo {len(collected)} partite disponibili")
        return collected[-index]


def white_eval(move: MoveAnalysis) -> str:
    """
    La valutazione sempre dal punto di vista del bianco.
    Internamente è relativa a chi ha mosso, ma a schermo cambierebbe
    segno a ogni riga e sarebbe illeggibile.
    """
    ev = move.eval_after if move.position.turn is Color.WHITE else move.eval_after.flipped()
    return str(ev)


def bar(win_percent: float, width: int = 6) -> str:
    filled = round(width * win_percent / 100)
    return "#" * filled + "." * (width - filled)


def print_moves(analysis: GameAnalysis, focus: Color | None) -> None:
    print(f"{'#':>5} {'mossa':<9} {'valut.':>8} {'persi':>7}  {'bianco':<7} {'':<3} migliore")
    print("-" * 70)

    for move in analysis.moves:
        pos = move.position
        if focus is not None and pos.turn is not focus:
            continue

        wp = move.win_percent_after
        white_wp = wp if pos.turn is Color.WHITE else 100.0 - wp

        number = f"{pos.move_number}{'.' if pos.turn is Color.WHITE else '…'}"
        drop = "     -" if move.is_opening else f"{move.win_percent_drop:5.1f}%"
        glyph = GLYPHS[move.classification]
        best = "" if move.is_best else f"({move.best_move_san})"
        label = LABELS[move.classification] if move.classification.is_notable else ""

        print(
            f"{number:>4} {pos.san:<9} {white_eval(move):>8} "
            f"{drop:>7}  {bar(white_wp):<7} {glyph:<3} {best:<9} {label}"
        )


def print_summary(analysis: GameAnalysis, color: Color) -> None:
    report = analysis.report(color)
    print(
        f"\n{color.value:<6} accuratezza {report.accuracy:5.1f}%   "
        f"ACPL {report.acpl:5.1f}   ({report.moves} mosse)"
    )
    parts = [
        f"{LABELS[k]} {report.count(k)}" for k in SUMMARY_ORDER if report.count(k) > 0
    ]
    print(f"       {' · '.join(parts)}")


def main() -> int:
    if find_stockfish() is None:
        print("Stockfish non trovato: apt install stockfish")
        return 1

    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    focus: Color | None = None

    if sys.argv[1] == "--pgn":
        pgn = open(sys.argv[2], encoding="utf-8").read()
        titolo = sys.argv[2]
    else:
        username = sys.argv[1]
        index = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        game = fetch_game(username, index)
        pgn = game.pgn
        focus = game.color_of(username)
        outcome = game.outcome_for(username)
        titolo = (
            f"{game.white.username} ({game.white.rating}) vs "
            f"{game.black.username} ({game.black.rating})\n"
            f"{game.started_at.date()}  {game.time_class}  "
            f"{game.opening_name or game.eco_code or ''}\n"
            f"Tu: {focus.value if focus else '?'}, "
            f"{outcome.value if outcome else '?'}\n"
            f"{game.url}"
        )

    parsed = parse_pgn(pgn)
    print(f"{titolo}\n")
    print(f"{len(parsed)} semimosse, profondità {SCAN_DEPTH} con riesame a {DEEP_DEPTH}\n")

    start = time.monotonic()
    with Engine(threads=THREADS, hash_mb=256) as engine:

        def progress(phase: Phase, done: int, total: int) -> None:
            fase = "scansione" if phase == "scan" else "riesame  "
            print(f"\r  {fase} {done}/{total}   ", end="", flush=True)

        analysis = analyse_game(engine, parsed, on_progress=progress)

    elapsed = time.monotonic() - start
    print(f"\r  analizzata in {elapsed:.1f}s ({analysis.deep_positions} riesami)\n")

    print_moves(analysis, focus)

    for color in (Color.WHITE, Color.BLACK):
        print_summary(analysis, color)

    notable = analysis.notable(focus)
    if notable:
        print("\nMosse da rivedere:")
        for move in notable:
            pos = move.position
            number = f"{pos.move_number}{'.' if pos.turn is Color.WHITE else '…'}"
            meglio = "" if move.is_best else f"  meglio {move.best_move_san}"
            tempo = (
                f"  [{move.position.time_spent:.0f}s]"
                if move.position.time_spent is not None
                else ""
            )
            print(
                f"  {number:>4} {pos.san:<8} {LABELS[move.classification]:<16}"
                f"{meglio:<18}{tempo}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
