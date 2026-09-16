"""
Payload di esempio, modellati su risposte reali dell'API.

Sta in un modulo suo e non in conftest.py: conftest è un file speciale
di pytest, che lo carica da sé, e importarlo direttamente crea problemi
di package. Qui invece è un normale modulo importabile.
"""

from __future__ import annotations

from typing import Any

ARCHIVES_PAYLOAD: dict[str, Any] = {
    "archives": [
        "https://api.chess.com/pub/player/cruciat/games/2025/11",
        "https://api.chess.com/pub/player/cruciat/games/2026/01",
        "https://api.chess.com/pub/player/cruciat/games/2025/12",
    ]
}

#: Struttura identica a quella reale: tag completi, e mosse con i tempi.
SHORT_PGN = (
    '[Event "Live Chess"]\n'
    '[Site "Chess.com"]\n'
    '[Date "2026.09.07"]\n'
    '[White "Cruciat"]\n'
    '[Black "avversario"]\n'
    '[Result "1-0"]\n'
    '[ECO "C20"]\n'
    '[ECOUrl "https://www.chess.com/openings/C20-Kings-Pawn-Opening"]\n'
    '[UTCDate "2026.09.07"]\n'
    '[UTCTime "19:23:17"]\n'
    '[WhiteElo "977"]\n'
    '[BlackElo "958"]\n'
    '[TimeControl "180+2"]\n'
    '[Termination "Cruciat won by checkmate"]\n\n'
    "1. e4 {[%clk 0:03:00.5]} 1... e5 {[%clk 0:03:00.2]} "
    "2. Qh5 {[%clk 0:03:01.9]} 2... Nc6 {[%clk 0:03:01.2]} "
    "3. Bc4 {[%clk 0:03:03.4]} 3... Nf6 {[%clk 0:03:00.9]} "
    "4. Qxf7# {[%clk 0:03:04.8]} 1-0\n"
)


def game_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "url": "https://www.chess.com/game/live/1111",
        "pgn": SHORT_PGN,
        "time_control": "180+2",
        "end_time": 1_760_000_000,
        "rated": True,
        "time_class": "blitz",
        "rules": "chess",
        "uuid": "abc-123",
        "white": {"username": "Cruciat", "rating": 977, "result": "win"},
        "black": {"username": "avversario", "rating": 958, "result": "checkmated"},
    }
    base.update(overrides)
    return base
