"""
Passa tutto l'archivio di un giocatore attraverso il parser.

Nove anni di partite vere trovano i casi limite che nessun test
scritto a mano immagina. Non asserisce nulla: raccoglie e riferisce.

Uso: python scripts/verifica_parsing.py USERNAME [MESI_DA_CONTROLLARE]
"""

from __future__ import annotations

import statistics
import sys
from collections import Counter

from chessreview.chesscom import ChessComClient
from chessreview.positions import PgnError, parse_pgn


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/verifica_parsing.py USERNAME [MESI]")
        return 1

    username = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 12

    totale = 0
    falliti = 0
    varianti = 0
    senza_orologio = 0
    lunghezze: list[int] = []
    errori: Counter[str] = Counter()
    esempi: list[tuple[str, str]] = []

    with ChessComClient(f"chessreview/0.1 ({username})") as client:
        archives = client.list_archives(username)
        selezionati = archives[-limit:] if limit > 0 else archives
        print(f"Controllo {len(selezionati)} mesi, da {selezionati[0]} a {selezionati[-1]}\n")

        for archive in selezionati:
            games = client.fetch_archive(archive, username)
            for game in games:
                totale += 1

                if not game.is_standard:
                    varianti += 1
                    continue

                try:
                    parsed = parse_pgn(game.pgn)
                except PgnError as exc:
                    falliti += 1
                    errori[str(exc)] += 1
                    if len(esempi) < 5:
                        esempi.append((game.url, str(exc)))
                    continue
                except Exception as exc:  # noqa: BLE001 — qui vogliamo vedere tutto
                    falliti += 1
                    errori[f"{type(exc).__name__}: {exc}"] += 1
                    if len(esempi) < 5:
                        esempi.append((game.url, f"{type(exc).__name__}: {exc}"))
                    continue

                lunghezze.append(len(parsed))
                if all(p.clock_after is None for p in parsed.positions):
                    senza_orologio += 1

            print(f"  {archive}: {len(games):>3} partite")

    print(f"\nPartite totali      {totale}")
    print(f"Varianti saltate    {varianti}")
    print(f"Parsing fallito     {falliti}")
    print(f"Senza orologio      {senza_orologio}")

    if lunghezze:
        print(f"\nSemimosse per partita")
        print(f"  minimo   {min(lunghezze)}")
        print(f"  mediana  {statistics.median(lunghezze):.0f}")
        print(f"  massimo  {max(lunghezze)}")
        print(f"  totale   {sum(lunghezze)}")
        # È il numero che conta per capire quanto costerà l'analisi.
        print(f"\nPosizioni da analizzare in tutto: {sum(lunghezze)}")

    if errori:
        print("\nErrori:")
        for messaggio, n in errori.most_common():
            print(f"  {n:>4}× {messaggio}")
        print("\nEsempi:")
        for url, messaggio in esempi:
            print(f"  {url}\n    {messaggio}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
