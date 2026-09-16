"""
Conversione dei modelli di dominio in JSON.

Vive separato dal dominio di proposito: le dataclass del motore
contengono oggetti Evaluation e tuple di varianti, forme comode
in Python e scomode da consumare in JavaScript. Tenere la traduzione
in un posto solo evita che il formato dell'API detti la forma
del dominio.
"""

from __future__ import annotations

from typing import Any

import chess

from ..analysis import GameAnalysis, MoveAnalysis, PlayerReport
from ..classification import LABELS
from ..engine import Evaluation
from ..models import Color, ImportedGame


def evaluation_json(evaluation: Evaluation) -> dict[str, Any]:
    return {
        "cp": evaluation.cp,
        "mate": evaluation.mate,
        "text": str(evaluation),
    }


def fen_after(fen_before: str, move_uci: str) -> str:
    """La posizione dopo la mossa, per la scacchiera del frontend."""
    board = chess.Board(fen_before)
    board.push(chess.Move.from_uci(move_uci))
    return board.fen()


def white_win_percent(move: MoveAnalysis) -> float:
    """
    Probabilità di vittoria del BIANCO dopo la mossa.

    Internamente le valutazioni sono relative a chi ha mosso, ma il
    grafico va letto come su qualunque sito di scacchi: linea in alto
    significa bianco meglio. La conversione si fa qui e una volta sola.
    """
    wp = move.win_percent_after
    return wp if move.position.turn is Color.WHITE else 100.0 - wp


def move_json(move: MoveAnalysis) -> dict[str, Any]:
    pos = move.position
    return {
        "ply": pos.ply,
        "moveNumber": pos.move_number,
        "turn": pos.turn.value,
        "san": pos.san,
        "uci": pos.uci,
        "fenBefore": pos.fen,
        "fenAfter": fen_after(pos.fen, pos.uci),
        "classification": move.classification.value,
        "label": LABELS[move.classification],
        "isMistake": move.classification.is_mistake,
        "isNotable": move.classification.is_notable,
        "evalBefore": evaluation_json(move.eval_before),
        "evalAfter": evaluation_json(move.eval_after),
        "whiteWinPercent": round(white_win_percent(move), 2),
        "winPercentDrop": round(move.win_percent_drop, 2),
        "accuracy": round(move.accuracy, 1),
        "bestMoveSan": move.best_move_san,
        "bestMoveUci": move.best_move_uci,
        "isBest": move.is_best,
        "isOpening": move.is_opening,
        "timeSpent": round(pos.time_spent, 1) if pos.time_spent is not None else None,
        "clockAfter": round(pos.clock_after, 1) if pos.clock_after is not None else None,
        "materialSacrificed": move.material_sacrificed,
        "depth": move.depth,
        # Le alternative servono al pannello "cosa si poteva fare".
        "alternatives": [
            {
                "san": line.move_san,
                "uci": line.move_uci,
                "eval": evaluation_json(line.evaluation),
            }
            for line in move.alternatives
        ],
    }


def report_json(report: PlayerReport) -> dict[str, Any]:
    return {
        "color": report.color.value,
        "moves": report.moves,
        "accuracy": round(report.accuracy, 1),
        "acpl": round(report.acpl, 1),
        "bestMoveRate": round(report.best_move_rate, 1),
        "counts": {klass.value: count for klass, count in report.counts.items()},
    }


def analysis_json(analysis: GameAnalysis, game: ImportedGame | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "moves": [move_json(m) for m in analysis.moves],
        "white": report_json(analysis.white),
        "black": report_json(analysis.black),
        "deepPositions": analysis.deep_positions,
    }
    if game is not None:
        payload["game"] = game_json(game)
    return payload


def game_json(game: ImportedGame, username: str | None = None) -> dict[str, Any]:
    """Metadati di una partita, per l'elenco e per l'intestazione."""
    color = game.color_of(username) if username else None
    outcome = game.outcome_for(username) if username else None

    return {
        "id": game.url,
        "url": game.url,
        "white": {
            "username": game.white.username,
            "rating": game.white.rating,
            "result": game.white.result,
        },
        "black": {
            "username": game.black.username,
            "rating": game.black.rating,
            "result": game.black.result,
        },
        "timeClass": game.time_class,
        "timeControl": game.time_control,
        "rated": game.rated,
        "playedAt": game.started_at.isoformat(),
        "eco": game.eco_code,
        "opening": game.opening_name,
        "termination": game.termination,
        "isStandard": game.is_standard,
        "yourColor": color.value if color else None,
        "yourOutcome": outcome.value if outcome else None,
    }
