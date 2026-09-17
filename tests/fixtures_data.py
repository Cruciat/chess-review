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


#: Risposta di /pub/player/{username}, coi campi che usiamo.
PROFILE_PAYLOAD: dict[str, Any] = {
    "avatar": "https://images.chesscomfiles.com/uploads/v1/user/1.jpeg",
    "player_id": 1,
    "url": "https://www.chess.com/member/Cruciat",
    "name": "Cruciat",
    "username": "cruciat",
    "followers": 10,
    "country": "https://api.chess.com/pub/country/IT",
    "last_online": 1_789_590_000,
    "joined": 1_496_534_400,
    "status": "basic",
    "is_streamer": False,
    "league": "Legend",
}

#: Risposta di /pub/player/{username}/stats: le cadenze mai giocate mancano.
STATS_PAYLOAD: dict[str, Any] = {
    "chess_daily": {
        "last": {"rating": 793, "date": 1_700_000_000, "rd": 120},
        "best": {"rating": 900, "date": 1_600_000_000, "game": "https://www.chess.com/game/daily/1"},
        "record": {"win": 10, "loss": 12, "draw": 1, "time_per_move": 3000, "timeout_percent": 0},
    },
    "chess_rapid": {
        "last": {"rating": 981, "date": 1_789_000_000, "rd": 60},
        "best": {"rating": 1050, "date": 1_700_000_000, "game": "https://www.chess.com/game/live/2"},
        "record": {"win": 120, "loss": 110, "draw": 9},
    },
    "chess_blitz": {
        "last": {"rating": 948, "date": 1_789_590_000, "rd": 45},
        "best": {"rating": 1012, "date": 1_750_000_000, "game": "https://www.chess.com/game/live/3"},
        "record": {"win": 800, "loss": 790, "draw": 40},
    },
    "fide": 0,
    "tactics": {"highest": {"rating": 1500, "date": 1}},
}
