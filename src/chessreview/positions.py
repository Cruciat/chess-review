"""
Da PGN a sequenza di posizioni analizzabili.

Il concetto portante: una Position rappresenta la situazione PRIMA
che la mossa venga giocata. È lì che il motore deve guardare, perché
è lì che esistono le alternative che il giocatore aveva davvero.
Modellare il contrario costringerebbe a sfasare di uno ogni indice
in tutti i calcoli successivi.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Iterator

import chess
import chess.pgn

from .models import Color

#: Valori standard per il bilancio del materiale. Servono al passo 6
#: per riconoscere i sacrifici: senza, la mossa brillante è indistinguibile.
PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

#: Commento dell'orologio: {[%clk 0:03:00.5]}
_CLOCK = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")


class PgnError(ValueError):
    """Il PGN non è leggibile o non contiene mosse."""


@dataclass(frozen=True)
class Position:
    """
    Una posizione e la mossa che vi è stata giocata.

    `ply` è il numero progressivo di semimossa a partire da zero:
    ply 0 è la prima mossa del bianco, ply 1 la prima del nero.
    `move_number` è invece il numero che compare nella notazione.
    """

    ply: int
    move_number: int
    turn: Color
    #: FEN della posizione prima della mossa: la chiave della cache.
    fen: str
    #: La mossa giocata, in notazione algebrica standard ("Nf3", "Qxf7#").
    san: str
    #: La stessa mossa in notazione UCI ("g1f3"), quella che parla Stockfish.
    uci: str
    #: Materiale di chi muove meno quello dell'avversario, prima della mossa.
    material_balance: int
    #: Pezzi totali sulla scacchiera, re esclusi: distingue apertura da finale.
    piece_count: int
    #: Secondi rimasti a chi ha mosso, dopo la mossa. None se il PGN non li ha.
    clock_after: float | None = None
    #: Secondi effettivamente spesi per pensare questa mossa.
    time_spent: float | None = None
    #: La mossa dà scacco all'avversario.
    gives_check: bool = False
    #: La mossa cattura un pezzo.
    is_capture: bool = False


@dataclass(frozen=True)
class ParsedGame:
    """Una partita pronta per l'analisi."""

    positions: tuple[Position, ...]
    #: FEN di partenza: diverso da quello standard solo nelle varianti.
    initial_fen: str
    #: FEN finale, utile per verificare l'esito.
    final_fen: str

    def __len__(self) -> int:
        return len(self.positions)

    def by_color(self, color: Color) -> list[Position]:
        """Solo le mosse di un giocatore: è la vista per gli insight."""
        return [p for p in self.positions if p.turn is color]

    def __iter__(self) -> Iterator[Position]:
        return iter(self.positions)


def parse_clock(comment: str) -> float | None:
    """Secondi rimasti, dal commento {[%clk 0:03:00.5]}."""
    match = _CLOCK.search(comment)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def material_balance(board: chess.Board) -> int:
    """
    Materiale di chi deve muovere meno quello dell'avversario.

    È relativo a chi muove e non al bianco di proposito: al passo 6
    la domanda sarà sempre "chi ha appena mosso ha dato via materiale?",
    e una grandezza già orientata evita un cambio di segno a ogni uso.
    """
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        if value == 0:
            continue
        total += value * len(board.pieces(piece_type, board.turn))
        total -= value * len(board.pieces(piece_type, not board.turn))
    return total


def piece_count(board: chess.Board) -> int:
    """Pezzi sulla scacchiera, re esclusi."""
    return sum(
        len(board.pieces(pt, color))
        for pt in PIECE_VALUES
        if PIECE_VALUES[pt] > 0
        for color in (chess.WHITE, chess.BLACK)
    )


def parse_pgn(pgn: str) -> ParsedGame:
    """
    Legge un PGN e restituisce la sequenza di posizioni.

    Solleva PgnError se il testo non è leggibile o non contiene mosse:
    capita con le partite abbandonate prima di muovere, che esistono
    negli archivi e non hanno nulla da analizzare.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise PgnError("PGN illeggibile")

    board = game.board()
    initial_fen = board.fen()

    # Secondi con cui parte ciascun giocatore, per calcolare il primo
    # tempo speso: senza, la prima mossa di ognuno non avrebbe misura.
    increment = 0.0
    previous_clock: dict[chess.Color, float | None] = {chess.WHITE: None, chess.BLACK: None}
    raw_tc = game.headers.get("TimeControl", "")
    if "+" in raw_tc:
        base, _, inc = raw_tc.partition("+")
        if base.isdigit() and inc.isdigit():
            previous_clock = {chess.WHITE: float(base), chess.BLACK: float(base)}
            increment = float(inc)
    elif raw_tc.isdigit():
        previous_clock = {chess.WHITE: float(raw_tc), chess.BLACK: float(raw_tc)}

    positions: list[Position] = []

    for ply, node in enumerate(game.mainline()):
        move = node.move
        if move is None:
            continue

        mover = board.turn
        clock_after = parse_clock(node.comment)

        # Tempo speso: quanto è sceso l'orologio di CHI HA MOSSO,
        # tenendo conto che l'incremento glielo ha appena restituito.
        spent: float | None = None
        before = previous_clock[mover]
        if clock_after is not None and before is not None:
            spent = max(0.0, before + increment - clock_after)
        if clock_after is not None:
            previous_clock[mover] = clock_after

        positions.append(
            Position(
                ply=ply,
                move_number=board.fullmove_number,
                turn=Color.WHITE if mover == chess.WHITE else Color.BLACK,
                fen=board.fen(),
                san=board.san(move),
                uci=move.uci(),
                material_balance=material_balance(board),
                piece_count=piece_count(board),
                clock_after=clock_after,
                time_spent=spent,
                gives_check=board.gives_check(move),
                is_capture=board.is_capture(move),
            )
        )

        board.push(move)

    if not positions:
        raise PgnError("PGN senza mosse")

    return ParsedGame(
        positions=tuple(positions),
        initial_fen=initial_fen,
        final_fen=board.fen(),
    )
