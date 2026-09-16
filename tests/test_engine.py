from __future__ import annotations

from typing import Iterator

import chess
import pytest

from chessreview.engine import (
    MATE_SCORE,
    Engine,
    Evaluation,
    Line,
    PositionAnalysis,
    find_stockfish,
)

#: I test che avviano davvero Stockfish si saltano se il binario manca,
#: così la suite resta eseguibile ovunque.
requires_engine = pytest.mark.skipif(
    find_stockfish() is None,
    reason="Stockfish non installato",
)


def line(rank: int, cp: int | None = None, mate: int | None = None) -> Line:
    return Line(
        rank=rank,
        move_uci="e2e4",
        move_san="e4",
        evaluation=Evaluation(cp=cp, mate=mate),
    )


#: Fixture a livello di modulo: come metodo di classe pytest la deprecherebbe.
@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine(threads=4, hash_mb=128) as eng:
        yield eng


class TestEvaluation:
    def test_centipawn_semplici(self) -> None:
        assert Evaluation(cp=150).to_cp() == 150
        assert Evaluation(cp=-80).to_cp() == -80

    def test_un_matto_vale_piu_di_qualsiasi_vantaggio(self) -> None:
        assert Evaluation(mate=5).to_cp() > Evaluation(cp=5000).to_cp()

    def test_matto_vicino_meglio_di_matto_lontano(self) -> None:
        assert Evaluation(mate=1).to_cp() > Evaluation(mate=8).to_cp()

    def test_matto_subito_e_negativo(self) -> None:
        assert Evaluation(mate=-3).to_cp() < 0
        assert Evaluation(mate=-3).to_cp() < Evaluation(cp=-5000).to_cp()

    def test_riconosce_i_matti(self) -> None:
        assert Evaluation(mate=2).is_mate
        assert Evaluation(mate=2).is_winning_mate
        assert not Evaluation(mate=-2).is_winning_mate
        assert not Evaluation(cp=900).is_mate

    def test_inversione_del_punto_di_vista(self) -> None:
        assert Evaluation(cp=120).flipped() == Evaluation(cp=-120)
        assert Evaluation(mate=3).flipped() == Evaluation(mate=-3)

    def test_inversione_doppia_torna_uguale(self) -> None:
        for ev in (Evaluation(cp=45), Evaluation(mate=-2), Evaluation(cp=0)):
            assert ev.flipped().flipped() == ev

    def test_resta_entro_i_limiti(self) -> None:
        assert abs(Evaluation(mate=1).to_cp()) <= MATE_SCORE

    def test_rappresentazione_leggibile(self) -> None:
        assert str(Evaluation(cp=150)) == "+1.50"
        assert str(Evaluation(cp=-75)) == "-0.75"
        assert str(Evaluation(mate=3)) == "#3"
        assert str(Evaluation(mate=-2)) == "#-2"


class TestPositionAnalysis:
    def test_la_migliore_e_la_prima(self) -> None:
        analysis = PositionAnalysis(fen="x", depth=18, lines=(line(1, cp=50), line(2, cp=10)))
        assert analysis.best.rank == 1
        assert analysis.evaluation.cp == 50

    def test_margine_sulla_seconda(self) -> None:
        analysis = PositionAnalysis(fen="x", depth=18, lines=(line(1, cp=200), line(2, cp=30)))
        assert analysis.margin_over_second == 170

    def test_senza_seconda_non_c_e_margine(self) -> None:
        analysis = PositionAnalysis(fen="x", depth=18, lines=(line(1, cp=200),))
        assert analysis.margin_over_second is None

    def test_trova_la_variante_di_una_mossa(self) -> None:
        lines = (
            Line(1, "e2e4", "e4", Evaluation(cp=30)),
            Line(2, "d2d4", "d4", Evaluation(cp=25)),
        )
        analysis = PositionAnalysis(fen="x", depth=18, lines=lines)
        found = analysis.line_for("d2d4")
        assert found is not None and found.move_san == "d4"
        assert analysis.line_for("a2a3") is None


@requires_engine
class TestConStockfish:
    def test_analizza_la_posizione_iniziale(self, engine: Engine) -> None:
        analysis = engine.analyse(chess.Board(), depth=10, multipv=3)
        assert len(analysis.lines) == 3
        # In apertura il vantaggio del bianco è piccolo.
        assert analysis.evaluation.cp is not None
        assert 0 <= analysis.evaluation.cp <= 100

    def test_ordina_le_varianti(self, engine: Engine) -> None:
        analysis = engine.analyse(chess.Board(), depth=10, multipv=4)
        ranks = [line.rank for line in analysis.lines]
        assert ranks == sorted(ranks)
        scores = [line.evaluation.to_cp() for line in analysis.lines]
        assert scores == sorted(scores, reverse=True)

    def test_trova_un_matto_in_uno(self, engine: Engine) -> None:
        # Matto del barbiere, una mossa prima della fine.
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        analysis = engine.analyse(board, depth=10, multipv=1)
        assert analysis.evaluation.mate == 1
        assert analysis.best.move_san == "Qxf7#"

    def test_vede_un_matto_subito(self, engine: Engine) -> None:
        # Re nero in a8, torre bianca in h7, re bianco in b6: il nero
        # deve muovere in b8 e subisce Th8 matto. Nessuna scappatoia.
        board = chess.Board("k7/7R/1K6/8/8/8/8/8 b - - 0 1")
        analysis = engine.analyse(board, depth=12, multipv=1)
        assert analysis.evaluation.mate is not None
        assert analysis.evaluation.mate < 0

    def test_la_valutazione_segue_chi_muove(self, engine: Engine) -> None:
        # Bianco senza donna. Con il bianco al tratto la valutazione
        # è negativa, con il nero al tratto positiva: stessa posizione,
        # punto di vista opposto.
        fen_bianco = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"
        fen_nero = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"

        bianco = engine.analyse_fen(fen_bianco, depth=8, multipv=1).evaluation
        nero = engine.analyse_fen(fen_nero, depth=8, multipv=1).evaluation

        assert bianco.to_cp() < -300
        assert nero.to_cp() > 300

    def test_riconosce_una_mossa_unica(self, engine: Engine) -> None:
        # Posizione dove la mossa migliore stacca nettamente le altre.
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        analysis = engine.analyse(board, depth=12, multipv=3)
        margin = analysis.margin_over_second
        assert margin is not None and margin > 500

    def test_non_chiede_piu_varianti_delle_mosse_legali(self, engine: Engine) -> None:
        # Posizione con poche mosse legali: il re deve scappare.
        board = chess.Board("7k/8/8/8/8/8/6q1/K7 w - - 0 1")
        analysis = engine.analyse(board, depth=6, multipv=5)
        assert len(analysis.lines) == board.legal_moves.count()

    def test_rifiuta_una_posizione_finita(self, engine: Engine) -> None:
        board = chess.Board(
            "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
        )
        assert board.is_game_over()
        with pytest.raises(ValueError):
            engine.analyse(board)
