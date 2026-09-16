"""
Dialogo con Stockfish.

Il protocollo UCI lo parla python-chess, non noi: qui c'è solo ciò che
serve al progetto, cioè valutare una posizione chiedendo le prime N
mosse, con i punteggi normalizzati in modo coerente.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from types import TracebackType

import chess
import chess.engine

#: Centipawn attribuiti a un matto, per poter ordinare. Non è una
#: valutazione vera: un matto non si misura in pedoni.
MATE_SCORE = 10_000

#: Quanto "vale meno" ogni mossa di distanza dal matto, così che
#: matto in 1 risulti preferibile a matto in 5.
MATE_STEP = 10

DEFAULT_DEPTH = 18
DEFAULT_MULTIPV = 3


class EngineNotFound(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Stockfish non trovato. Installalo con 'apt install stockfish' "
            "oppure indica il percorso con la variabile STOCKFISH_PATH."
        )


@dataclass(frozen=True)
class Evaluation:
    """
    Valutazione di una posizione, dal punto di vista di CHI DEVE MUOVERE.

    Sempre relativa a chi muove e mai al bianco: così confrontare la
    valutazione prima e dopo una mossa non richiede mai un cambio di segno.
    """

    #: Centipawn, se la valutazione non è un matto.
    cp: int | None = None
    #: Mosse al matto: positivo se lo dà chi muove, negativo se lo subisce.
    mate: int | None = None

    @property
    def is_mate(self) -> bool:
        return self.mate is not None

    @property
    def is_winning_mate(self) -> bool:
        return self.mate is not None and self.mate > 0

    def to_cp(self) -> int:
        """
        Valore in centipawn utilizzabile per ordinare e confrontare.
        I matti diventano valori molto grandi, più grandi quanto più
        il matto è vicino.
        """
        if self.mate is not None:
            magnitude = MATE_SCORE - min(abs(self.mate) * MATE_STEP, MATE_SCORE - 1)
            return magnitude if self.mate > 0 else -magnitude
        return self.cp if self.cp is not None else 0

    def flipped(self) -> Evaluation:
        """
        La stessa valutazione vista dall'altro giocatore.
        Serve perché dopo una mossa tocca all'avversario, e per
        confrontare le due posizioni bisogna riportarle allo stesso punto
        di vista.
        """
        return Evaluation(
            cp=-self.cp if self.cp is not None else None,
            mate=-self.mate if self.mate is not None else None,
        )

    def __str__(self) -> str:
        if self.mate is not None:
            return f"#{self.mate}" if self.mate > 0 else f"#-{abs(self.mate)}"
        return f"{(self.cp or 0) / 100:+.2f}"


@dataclass(frozen=True)
class Line:
    """Una delle mosse candidate restituite dal motore."""

    #: Posizione nella classifica: 1 è la migliore.
    rank: int
    move_uci: str
    move_san: str
    evaluation: Evaluation
    #: Seguito previsto, in notazione UCI.
    pv: tuple[str, ...] = ()
    depth: int = 0


@dataclass(frozen=True)
class PositionAnalysis:
    """Il risultato dell'analisi di una posizione."""

    fen: str
    depth: int
    lines: tuple[Line, ...]

    @property
    def best(self) -> Line:
        return self.lines[0]

    @property
    def evaluation(self) -> Evaluation:
        """La valutazione della posizione, cioè quella della mossa migliore."""
        return self.lines[0].evaluation

    def line_for(self, move_uci: str) -> Line | None:
        """La variante corrispondente a una mossa, se il motore l'ha calcolata."""
        for line in self.lines:
            if line.move_uci == move_uci:
                return line
        return None

    @property
    def margin_over_second(self) -> int | None:
        """
        Di quanti centipawn la mossa migliore supera la seconda.

        È la grandezza che distingue "c'era una sola mossa buona" da
        "ce n'erano diverse equivalenti", e senza di essa metà delle
        categorie di classificazione non è calcolabile.
        """
        if len(self.lines) < 2:
            return None
        return self.lines[0].evaluation.to_cp() - self.lines[1].evaluation.to_cp()


def find_stockfish() -> str | None:
    """Percorso del binario, dalla variabile d'ambiente o dal PATH."""
    from_env = os.environ.get("STOCKFISH_PATH")
    if from_env and os.path.isfile(from_env):
        return from_env
    return shutil.which("stockfish")


def _to_evaluation(score: chess.engine.PovScore, turn: chess.Color) -> Evaluation:
    """Converte il punteggio di python-chess, orientandolo su chi muove."""
    relative = score.pov(turn)
    mate = relative.mate()
    if mate is not None:
        return Evaluation(mate=mate)
    return Evaluation(cp=relative.score())


class Engine:
    """
    Stockfish, avviato una volta e riusato per tutte le posizioni.

    Riavviare il processo a ogni posizione moltiplicherebbe i tempi:
    una partita sono una cinquantina di posizioni.
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        threads: int = 1,
        hash_mb: int = 128,
    ) -> None:
        binary = path or find_stockfish()
        if binary is None:
            raise EngineNotFound()

        self.path = binary
        self._engine = chess.engine.SimpleEngine.popen_uci(binary)
        self._engine.configure({"Threads": threads, "Hash": hash_mb})

    # -- gestione della risorsa ------------------------------------------

    def close(self) -> None:
        self._engine.quit()

    def __enter__(self) -> Engine:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- analisi -----------------------------------------------------------

    def analyse(
        self,
        board: chess.Board,
        *,
        depth: int = DEFAULT_DEPTH,
        multipv: int = DEFAULT_MULTIPV,
    ) -> PositionAnalysis:
        """
        Le prime `multipv` mosse della posizione, ordinate dalla migliore.

        Solleva ValueError se la partita è già finita: non c'è nulla da
        analizzare e Stockfish non risponderebbe.
        """
        if board.is_game_over():
            raise ValueError("Posizione terminale: niente da analizzare")

        # Non si possono chiedere più varianti di quante siano le mosse legali.
        wanted = max(1, min(multipv, board.legal_moves.count()))

        infos = self._engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=wanted,
        )

        lines: list[Line] = []
        for info in infos:
            pv = info.get("pv")
            if not pv:
                continue

            move = pv[0]
            score = info.get("score")
            if score is None:
                continue

            lines.append(
                Line(
                    rank=int(info.get("multipv", len(lines) + 1)),
                    move_uci=move.uci(),
                    move_san=board.san(move),
                    evaluation=_to_evaluation(score, board.turn),
                    pv=tuple(m.uci() for m in pv),
                    depth=int(info.get("depth", depth)),
                )
            )

        if not lines:
            raise RuntimeError(f"Stockfish non ha restituito varianti per {board.fen()}")

        lines.sort(key=lambda line: line.rank)
        return PositionAnalysis(fen=board.fen(), depth=depth, lines=tuple(lines))

    def analyse_fen(
        self,
        fen: str,
        *,
        depth: int = DEFAULT_DEPTH,
        multipv: int = DEFAULT_MULTIPV,
    ) -> PositionAnalysis:
        return self.analyse(chess.Board(fen), depth=depth, multipv=multipv)
