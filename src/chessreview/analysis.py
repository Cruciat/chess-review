"""
Analisi di una partita intera.

La strategia è a due passate. Una prima passata veloce su tutte le
posizioni serve solo a individuare dove la valutazione è crollata;
una seconda passata profonda va solo su quelle. La stragrande
maggioranza delle mosse di una partita è ovvia (ricatture forzate,
sviluppi, mosse uniche) e non merita profondità.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Sequence

import chess

from .classification import (
    DEFAULT_THRESHOLDS,
    MoveClass,
    MoveContext,
    Thresholds,
    classify,
)
from .engine import Engine, Evaluation, Line
from .models import Color
from .positions import ParsedGame, Position
from .scoring import (
    average_centipawn_loss,
    game_accuracy,
    move_accuracy,
    win_percent,
    win_percent_lost,
)

#: Profondità della prima passata: basta a vedere i crolli.
SCAN_DEPTH = 12

#: Profondità della seconda passata, sulle sole posizioni sospette.
DEEP_DEPTH = 18

#: Sopra questa perdita di probabilità la posizione viene riesaminata.
#: Volutamente bassa: meglio approfondire venti posizioni inutili
#: che lasciarsi sfuggire un errore vero.
REVIEW_THRESHOLD = 3.0

#: Semimosse iniziali considerate apertura e non giudicate.
OPENING_PLIES = 8

MULTIPV = 3

#: L'ACPL esplode quando la posizione è già decisa: a ±5 i centipawn
#: non dicono più nulla. Si limita per mossa, altrimenti una partita
#: persa male produce numeri come 863 che non significano niente.
ACPL_CAP = 300


@dataclass(frozen=True)
class MoveAnalysis:
    """Il giudizio su una singola mossa."""

    position: Position
    classification: MoveClass

    #: Valutazione della posizione prima della mossa, per chi muove.
    eval_before: Evaluation
    #: Valutazione dopo la mossa, già riportata al punto di vista di chi ha mosso.
    eval_after: Evaluation

    #: La mossa che il motore avrebbe giocato.
    best_move_san: str
    best_move_uci: str
    #: Le alternative calcolate, per mostrare cosa si poteva fare.
    alternatives: tuple[Line, ...]

    #: Di quanto la migliore supera la seconda: identifica le mosse uniche.
    margin_over_second: int | None

    #: Punti percentuali di probabilità di vittoria persi.
    win_percent_drop: float
    #: Centipawn persi rispetto alla mossa migliore, limitati.
    centipawn_loss: int
    #: Profondità effettivamente usata: bassa in scansione, alta nel riesame.
    depth: int
    #: Materiale dato via dalla mossa, secondo la static exchange evaluation.
    material_sacrificed: int

    is_best: bool
    is_opening: bool

    @property
    def accuracy(self) -> float:
        return move_accuracy(self.win_percent_drop)

    @property
    def win_percent_before(self) -> float:
        return win_percent(self.eval_before)

    @property
    def win_percent_after(self) -> float:
        return win_percent(self.eval_after)


@dataclass(frozen=True)
class PlayerReport:
    """I numeri di un giocatore in una partita."""

    color: Color
    moves: int
    accuracy: float
    acpl: float
    best_moves: int
    counts: dict[MoveClass, int]

    @property
    def best_move_rate(self) -> float:
        return 100.0 * self.best_moves / self.moves if self.moves else 0.0

    def count(self, klass: MoveClass) -> int:
        return self.counts.get(klass, 0)


@dataclass(frozen=True)
class GameAnalysis:
    """L'analisi completa di una partita."""

    moves: tuple[MoveAnalysis, ...]
    white: PlayerReport
    black: PlayerReport
    deep_positions: int

    def report(self, color: Color) -> PlayerReport:
        return self.white if color is Color.WHITE else self.black

    def for_color(self, color: Color) -> list[MoveAnalysis]:
        return [m for m in self.moves if m.position.turn is color]

    def notable(self, color: Color | None = None) -> list[MoveAnalysis]:
        """Le mosse che meritano un commento, in ordine di partita."""
        return [
            m
            for m in self.moves
            if m.classification.is_notable and (color is None or m.position.turn is color)
        ]


ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class _Raw:
    """Risultato grezzo dell'analisi di una posizione, prima del giudizio."""

    eval_before: Evaluation
    eval_after: Evaluation
    best_san: str
    best_uci: str
    margin: int | None
    alternatives: tuple[Line, ...]
    legal_moves: int


def _evaluate_position(
    engine: Engine,
    position: Position,
    depth: int,
    *,
    known_before: Evaluation | None = None,
) -> _Raw:
    """
    Valuta una posizione e la mossa che vi è stata giocata.

    `known_before` permette di riusare la valutazione già calcolata come
    "dopo" della mossa precedente: sono la stessa posizione, e ricalcolarla
    raddoppierebbe il costo dell'intera analisi. Le alternative però
    servono comunque, quindi l'analisi si fa lo stesso: il riuso vale
    solo per l'analisi della posizione DOPO la mossa.
    """
    board = chess.Board(position.fen)
    legal_moves = board.legal_moves.count()
    analysis = engine.analyse(board, depth=depth, multipv=MULTIPV)

    eval_before = known_before if known_before is not None else analysis.evaluation
    best = analysis.best

    # La mossa giocata potrebbe già essere fra le varianti calcolate:
    # in quel caso il motore ha già fatto il lavoro.
    played = analysis.line_for(position.uci)
    if played is not None:
        eval_after = played.evaluation
    else:
        board.push(chess.Move.from_uci(position.uci))
        if board.is_game_over():
            # Posizione terminale: il motore non la analizzerebbe.
            outcome = board.outcome()
            if outcome is not None and outcome.winner is not None:
                eval_after = Evaluation(mate=1)
            else:
                eval_after = Evaluation(cp=0)
        else:
            after = engine.analyse(board, depth=depth, multipv=1)
            # Vista dall'avversario: va riportata a chi ha mosso.
            eval_after = after.evaluation.flipped()

    return _Raw(
        eval_before=eval_before,
        eval_after=eval_after,
        best_san=best.move_san,
        best_uci=best.move_uci,
        margin=analysis.margin_over_second,
        alternatives=analysis.lines,
        legal_moves=legal_moves,
    )


def _build(
    position: Position,
    raw: _Raw,
    depth: int,
    is_opening: bool,
    thresholds: Thresholds,
) -> MoveAnalysis:
    from .classification import material_sacrificed

    drop = win_percent_lost(raw.eval_before, raw.eval_after)
    loss = min(ACPL_CAP, max(0, raw.eval_before.to_cp() - raw.eval_after.to_cp()))
    is_best = position.uci == raw.best_uci

    context = MoveContext(
        fen_before=position.fen,
        move_uci=position.uci,
        is_best=is_best,
        is_opening=is_opening,
        win_percent_drop=drop,
        win_percent_before=win_percent(raw.eval_before),
        win_percent_after=win_percent(raw.eval_after),
        eval_before=raw.eval_before,
        eval_after=raw.eval_after,
        margin_over_second=raw.margin,
        legal_move_count=raw.legal_moves,
    )

    return MoveAnalysis(
        position=position,
        classification=classify(context, thresholds),
        eval_before=raw.eval_before,
        eval_after=raw.eval_after,
        best_move_san=raw.best_san,
        best_move_uci=raw.best_uci,
        alternatives=raw.alternatives,
        margin_over_second=raw.margin,
        win_percent_drop=drop,
        centipawn_loss=loss,
        depth=depth,
        material_sacrificed=material_sacrificed(position.fen, position.uci),
        is_best=is_best,
        is_opening=is_opening,
    )


def analyse_game(
    engine: Engine,
    game: ParsedGame,
    *,
    scan_depth: int = SCAN_DEPTH,
    deep_depth: int = DEEP_DEPTH,
    review_threshold: float = REVIEW_THRESHOLD,
    opening_plies: int = OPENING_PLIES,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    on_progress: ProgressCallback | None = None,
) -> GameAnalysis:
    """
    Analizza una partita con la strategia a due passate.

    `on_progress` viene chiamata con (fatte, totali) durante la prima
    passata, che è quella lunga.
    """
    positions: Sequence[Position] = game.positions
    total = len(positions)

    # -- prima passata: veloce, su tutto -------------------------------
    scanned: list[tuple[Position, _Raw, bool]] = []

    # La valutazione "dopo" una mossa è la valutazione "prima" della
    # successiva: sono la stessa posizione. Riusarla dimezza il lavoro.
    carried: Evaluation | None = None

    for index, position in enumerate(positions):
        raw = _evaluate_position(engine, position, scan_depth, known_before=carried)
        scanned.append((position, raw, position.ply < opening_plies))
        carried = raw.eval_after.flipped()

        if on_progress is not None:
            on_progress(index + 1, total)

    # -- seconda passata: profonda, solo dove serve ---------------------
    final: list[MoveAnalysis] = []
    deep_count = 0

    for position, raw, is_opening in scanned:
        drop = win_percent_lost(raw.eval_before, raw.eval_after)
        needs_review = drop >= review_threshold and not is_opening

        if not needs_review:
            final.append(_build(position, raw, scan_depth, is_opening, thresholds))
            continue

        deep_count += 1
        deep = _evaluate_position(engine, position, deep_depth)
        final.append(_build(position, deep, deep_depth, is_opening, thresholds))

    moves = tuple(final)
    return GameAnalysis(
        moves=moves,
        white=_player_report(moves, Color.WHITE),
        black=_player_report(moves, Color.BLACK),
        deep_positions=deep_count,
    )


def _player_report(moves: Sequence[MoveAnalysis], color: Color) -> PlayerReport:
    """
    I numeri di un giocatore, escludendo le mosse di apertura:
    includerle gonfierebbe l'accuratezza di chiunque, perché
    le prime mosse sono quasi sempre corrette.
    """
    own = [m for m in moves if m.position.turn is color and not m.is_opening]
    if not own:
        return PlayerReport(
            color=color, moves=0, accuracy=100.0, acpl=0.0, best_moves=0, counts={}
        )

    counts = Counter(m.classification for m in own)

    return PlayerReport(
        color=color,
        moves=len(own),
        accuracy=game_accuracy([m.win_percent_drop for m in own]),
        acpl=average_centipawn_loss([m.centipawn_loss for m in own]),
        best_moves=sum(1 for m in own if m.is_best),
        counts=dict(counts),
    )
