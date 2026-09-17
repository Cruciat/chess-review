"""
Classificazione delle mosse.

L'ORDINE DEI CONTROLLI È LA COSA PIÙ IMPORTANTE DI QUESTO MODULO.
Le categorie non stanno su una scala: una mossa brillante perde
pochissima probabilità di vittoria, quindi controllare per prima
la perdita la etichetterebbe come "ottima" e la brillantezza non
verrebbe mai riconosciuta. Si va dal più specifico al più generico.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import chess

from .engine import Evaluation

#: Valori standard, in unità di pedone.
PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


class MoveClass(str, Enum):
    """
    Le categorie, dalla migliore alla peggiore.

    I nomi sono nostri: chess.com chiede di non riusare i propri
    glifi di classificazione, e comunque avere etichette proprie
    ci lascia liberi di aggiungerne.
    """

    BRILLIANT = "brilliant"
    """Sacrificio corretto: dà via materiale e la mossa resta ottima."""

    CRITICAL = "critical"
    """Unica mossa che tiene: tutte le alternative peggioravano."""

    BEST = "best"
    """La mossa che il motore avrebbe giocato."""

    EXCELLENT = "excellent"
    """Non la migliore ma equivalente."""

    GOOD = "good"
    """Ragionevole, si perde qualcosina."""

    INACCURACY = "inaccuracy"
    """Imprecisione: la posizione peggiora in modo percettibile."""

    MISTAKE = "mistake"
    """Errore: si butta via una parte consistente del vantaggio."""

    BLUNDER = "blunder"
    """Errore grave: la partita cambia di segno."""

    MISSED_WIN = "missed_win"
    """Avevi una posizione vinta o un matto e l'hai lasciata andare."""

    BOOK = "book"
    """Mossa di apertura: non viene giudicata."""

    FORCED = "forced"
    """Unica mossa legale: non c'era niente da scegliere."""

    @property
    def is_mistake(self) -> bool:
        return self in _MISTAKES

    @property
    def is_notable(self) -> bool:
        """Merita di essere segnalata, in positivo o in negativo."""
        return self in _NOTABLE


_MISTAKES = frozenset(
    {MoveClass.INACCURACY, MoveClass.MISTAKE, MoveClass.BLUNDER, MoveClass.MISSED_WIN}
)

_NOTABLE = _MISTAKES | {MoveClass.BRILLIANT, MoveClass.CRITICAL}

#: Etichette leggibili, per il terminale e per l'interfaccia.
LABELS: dict[MoveClass, str] = {
    MoveClass.BRILLIANT: "Brillante",
    MoveClass.CRITICAL: "Unica",
    MoveClass.BEST: "Migliore",
    MoveClass.EXCELLENT: "Ottima",
    MoveClass.GOOD: "Buona",
    MoveClass.INACCURACY: "Imprecisione",
    MoveClass.MISTAKE: "Errore",
    MoveClass.BLUNDER: "Blunder",
    MoveClass.MISSED_WIN: "Vittoria mancata",
    MoveClass.BOOK: "Libro",
    MoveClass.FORCED: "Forzata",
}


@dataclass(frozen=True)
class Thresholds:
    """
    Le soglie del classificatore, in punti percentuali di probabilità
    di vittoria persa.

    I valori di partenza sono tarati sulla distribuzione osservata in
    partite blitz a 180+2: la gran parte delle mosse sta sotto il 2%,
    gli errori veri stanno sopra il 10%. In partite lunghe converrebbe
    stringerli, perché lì si sbaglia meno e più piccolo.
    """

    excellent: float = 2.0
    good: float = 5.0
    inaccuracy: float = 10.0
    mistake: float = 20.0

    #: Sopra questa probabilità di vittoria la posizione è considerata vinta.
    winning: float = 90.0
    #: Sotto questa, dopo una mossa, la vittoria è stata persa.
    lost_win: float = 60.0

    #: Distacco minimo fra la migliore e la seconda, in punti di probabilità
    #: di vittoria, perché la migliore sia "unica".
    #:
    #: È in win% e non in centipawn per due motivi. Un matto vale 10000
    #: centipawn, quindi qualunque matto superava la soglia anche con
    #: alternative comodamente vincenti. E in posizioni già decise un
    #: distacco di qualche pedone non cambia nulla, mentre la win% lo
    #: sconta da sola. 20 punti corrispondono circa a 250 centipawn
    #: a partire da una posizione pari.
    critical_margin: float = 20.0
    #: Perdita massima perché una mossa unica conti come tale.
    critical_max_drop: float = 2.0

    #: Materiale minimo sacrificato perché si parli di sacrificio.
    sacrifice_material: int = 2
    #: Perdita massima perché un sacrificio sia brillante.
    brilliant_max_drop: float = 2.0
    #: Se senza la mossa giocata avevi comunque almeno questa probabilità
    #: di vittoria, il sacrificio non è brillante: quando avresti vinto lo
    #: stesso, dare via un pezzo non è un merito. Si guarda la migliore
    #: alternativa e non la posizione, altrimenti un sacrificio che forza
    #: il matto risulterebbe "già vinto" proprio grazie a sé stesso.
    brilliant_max_win: float = 85.0


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class MoveContext:
    """
    Tutto ciò che serve a classificare una mossa.

    Vive separato da MoveAnalysis di proposito: così il classificatore
    è una funzione pura, testabile costruendo casi a mano senza avviare
    Stockfish.
    """

    fen_before: str
    move_uci: str
    is_best: bool
    is_opening: bool
    win_percent_drop: float
    win_percent_before: float
    win_percent_after: float
    eval_before: Evaluation
    eval_after: Evaluation
    #: Di quanto la migliore supera la seconda, in punti di win%.
    win_margin_over_second: float | None
    legal_move_count: int
    #: Casella su cui l'avversario ha appena catturato, se la sua ultima
    #: mossa era una cattura. Serve a riconoscere le ricatture, e dal solo
    #: FEN non è ricavabile: il FEN non contiene la mossa precedente.
    previous_capture_square: str | None = None


def _material(board: chess.Board, color: chess.Color) -> int:
    """Materiale di un colore, in unità di pedone."""
    return sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in PIECE_VALUES.items()
        if value > 0
    )


def material_sacrificed(fen: str, move_uci: str) -> int:
    """
    Materiale che la mossa mette a disposizione dell'avversario.

    Il calcolo è diretto invece che affidato a una static exchange
    evaluation della libreria, che non è disponibile in tutte le
    versioni di python-chess: si simula la migliore cattura
    dell'avversario sulla casella di arrivo e la nostra migliore
    ricattura, e si guarda il bilancio.

    Un valore positivo significa che dopo lo scambio hai meno materiale
    di prima: è la definizione operativa di sacrificio, ed è ciò che
    rende riconoscibile la mossa brillante.
    """
    board = chess.Board(fen)
    move = chess.Move.from_uci(move_uci)
    if move not in board.legal_moves:
        return 0

    mover = board.turn
    before = _material(board, mover) - _material(board, not mover)

    board.push(move)
    target = move.to_square

    # L'avversario può catturare il pezzo appena mosso?
    captures = [
        m for m in board.legal_moves if m.to_square == target and board.is_capture(m)
    ]
    if not captures:
        return 0

    worst = before

    for capture in captures:
        board.push(capture)

        # La nostra migliore ricattura sulla stessa casella, se c'è.
        recaptures = [
            m for m in board.legal_moves if m.to_square == target and board.is_capture(m)
        ]
        if recaptures:
            # Si riprende con il pezzo di minor valore: è la ricattura
            # che conviene, e quella che l'avversario deve mettere in conto.
            def piece_value(m: chess.Move) -> int:
                piece = board.piece_at(m.from_square)
                return PIECE_VALUES[piece.piece_type] if piece else 0

            best_recapture = min(recaptures, key=piece_value)
            board.push(best_recapture)
            balance = _material(board, mover) - _material(board, not mover)
            board.pop()
        else:
            balance = _material(board, mover) - _material(board, not mover)

        board.pop()
        worst = min(worst, balance)

    # Positivo se abbiamo perso materiale rispetto a prima della mossa.
    return max(0, before - worst)


def is_trivial_recapture(
    fen: str,
    move_uci: str,
    previous_capture_square: str | None,
) -> bool:
    """
    La mossa riprende semplicemente un pezzo appena catturato.

    Serve a non gonfiare la categoria "unica": una ricattura forzata
    stacca sempre nettamente dalle alternative, ma trovarla non è
    un merito, è l'unica cosa sensata da fare.

    Una ricattura è una cattura sulla stessa casella su cui l'avversario
    ha appena catturato. La casella va passata da fuori perché il FEN
    non conserva la mossa precedente: la versione di prima provava a
    dedurla dal contatore delle semimosse, che però si azzera anche
    dopo una cattura altrove e dopo qualunque mossa di pedone.
    """
    if previous_capture_square is None:
        return False

    board = chess.Board(fen)
    move = chess.Move.from_uci(move_uci)
    if move not in board.legal_moves or not board.is_capture(move):
        return False

    return chess.square_name(move.to_square) == previous_capture_square


def classify(
    context: MoveContext,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> MoveClass:
    """
    L'etichetta di una mossa.

    L'ordine dei controlli è deliberato e va dal più specifico al più
    generico: invertirlo renderebbe invisibili le categorie speciali.
    """
    # 1. Apertura: non si giudica quello che è teoria nota.
    if context.is_opening:
        return MoveClass.BOOK

    # 2. Nessuna scelta, nessun merito e nessuna colpa.
    if context.legal_move_count == 1:
        return MoveClass.FORCED

    # 3. Vittoria buttata via. Va prima della scala delle perdite
    #    perché è un errore di natura diversa: non hai peggiorato
    #    la posizione, hai smesso di vincerla.
    if (
        context.win_percent_before >= thresholds.winning
        and context.win_percent_after < thresholds.lost_win
    ):
        return MoveClass.MISSED_WIN

    # 4. Brillante: prima di tutto ciò che riguarda la perdita, perché
    #    una mossa brillante ne perde pochissima e verrebbe assorbita
    #    dalla categoria "migliore" senza essere riconosciuta.
    if _is_brilliant(context, thresholds):
        return MoveClass.BRILLIANT

    # 5. Unica mossa che tiene: merito vero, ma solo se l'hai trovata
    #    e se non era una ricattura ovvia.
    if (
        context.is_best
        and context.win_margin_over_second is not None
        and context.win_margin_over_second >= thresholds.critical_margin
        and context.win_percent_drop <= thresholds.critical_max_drop
        and not is_trivial_recapture(
            context.fen_before, context.move_uci, context.previous_capture_square
        )
    ):
        return MoveClass.CRITICAL

    # 6. La scala delle perdite.
    drop = context.win_percent_drop
    if context.is_best:
        return MoveClass.BEST
    if drop < thresholds.excellent:
        return MoveClass.EXCELLENT
    if drop < thresholds.good:
        return MoveClass.GOOD
    if drop < thresholds.inaccuracy:
        return MoveClass.INACCURACY
    if drop < thresholds.mistake:
        return MoveClass.MISTAKE
    return MoveClass.BLUNDER


def _is_brilliant(context: MoveContext, thresholds: Thresholds) -> bool:
    """
    Quattro condizioni insieme, e servono tutte.

    1. la mossa è buona: perde pochissima probabilità di vittoria
    2. sacrifica materiale che l'avversario può davvero prendere
    3. senza questa mossa non si vinceva comunque: sacrificare a +10 con
       dieci alternative vincenti non è brillante, è indifferente
    4. non era l'unica mossa legale: se non c'era scelta, non hai scelto
    """
    if context.win_percent_drop > thresholds.brilliant_max_drop:
        return False
    if _best_alternative_win(context) > thresholds.brilliant_max_win:
        return False
    if context.legal_move_count < 2:
        return False

    sacrificed = material_sacrificed(context.fen_before, context.move_uci)
    return sacrificed >= thresholds.sacrifice_material


def _best_alternative_win(context: MoveContext) -> float:
    """
    Probabilità di vittoria della migliore mossa diversa da quella giocata.

    Se la mossa giocata non è la migliore, l'alternativa è la migliore
    stessa. Se lo è, l'alternativa è la seconda, che si ricava dal
    distacco. Senza distacco noto si torna alla posizione: è la stima
    prudente, che nel dubbio non concede la brillantezza.
    """
    if context.is_best and context.win_margin_over_second is not None:
        return context.win_percent_before - context.win_margin_over_second
    return context.win_percent_before
