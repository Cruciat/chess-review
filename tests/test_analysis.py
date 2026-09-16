from __future__ import annotations

from typing import Iterator

import pytest

from chessreview.analysis import analyse_game
from chessreview.engine import Engine, find_stockfish
from chessreview.models import Color
from chessreview.positions import parse_pgn

from fixtures_data import SHORT_PGN

requires_engine = pytest.mark.skipif(
    find_stockfish() is None,
    reason="Stockfish non installato",
)

#: Tranello di Légal. Il nero prende la donna con 6...Bxd1 e viene
#: mattato in due: è il blunder ideale per un test, perché la mossa
#: sembra ottima (guadagna una donna) ed è invece perdente.
LEGAL_TRAP = (
    '[TimeControl "600"]\n\n'
    "1. e4 e5 2. Nf3 Nc6 3. Bc4 d6 4. Nc3 Bg4 5. h3 Bh5 "
    "6. Nxe5 Bxd1 7. Bxf7+ Ke7 8. Nd5# 1-0"
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine(threads=4, hash_mb=128) as eng:
        yield eng


@requires_engine
class TestAnalisiDiPartita:
    def test_analizza_ogni_mossa(self, engine: Engine) -> None:
        game = parse_pgn(SHORT_PGN)
        analysis = analyse_game(engine, game, scan_depth=8, deep_depth=10)
        assert len(analysis.moves) == len(game)

    def test_conserva_l_ordine_delle_mosse(self, engine: Engine) -> None:
        game = parse_pgn(SHORT_PGN)
        analysis = analyse_game(engine, game, scan_depth=8, deep_depth=10)
        assert [m.position.ply for m in analysis.moves] == list(range(len(game)))

    def test_marca_le_mosse_di_apertura(self, engine: Engine) -> None:
        game = parse_pgn(SHORT_PGN)
        analysis = analyse_game(engine, game, scan_depth=8, deep_depth=10, opening_plies=4)
        assert [m.is_opening for m in analysis.moves[:4]] == [True] * 4
        assert not analysis.moves[4].is_opening

    def test_le_perdite_non_sono_mai_negative(self, engine: Engine) -> None:
        game = parse_pgn(LEGAL_TRAP)
        analysis = analyse_game(engine, game, scan_depth=8, deep_depth=10)
        assert all(m.win_percent_drop >= 0 for m in analysis.moves)
        assert all(m.centipawn_loss >= 0 for m in analysis.moves)

    def test_riconosce_il_blunder(self, engine: Engine) -> None:
        game = parse_pgn(LEGAL_TRAP)
        analysis = analyse_game(engine, game, scan_depth=10, deep_depth=14)
        peggiore = max(analysis.for_color(Color.BLACK), key=lambda m: m.win_percent_drop)
        assert peggiore.position.san == "Bxd1"
        assert peggiore.win_percent_drop > 20.0

    def test_le_mosse_ovvie_non_perdono_quasi_nulla(self, engine: Engine) -> None:
        # È la verifica che il calcolo non sia sfasato: in una partita
        # normale la maggioranza delle mosse deve perdere pochissimo.
        game = parse_pgn(LEGAL_TRAP)
        analysis = analyse_game(engine, game, scan_depth=10, deep_depth=12)
        piccole = [m for m in analysis.moves if m.win_percent_drop < 5.0]
        assert len(piccole) > len(analysis.moves) / 2

    def test_la_seconda_passata_tocca_poche_posizioni(self, engine: Engine) -> None:
        game = parse_pgn(LEGAL_TRAP)
        analysis = analyse_game(engine, game, scan_depth=10, deep_depth=12)
        # Se riesaminasse quasi tutto, la strategia a due passate
        # non servirebbe a niente: è il sintomo del calcolo sfasato.
        assert analysis.deep_positions <= len(analysis.moves) / 3

    def test_le_posizioni_riesaminate_hanno_profondita_maggiore(self, engine: Engine) -> None:
        game = parse_pgn(LEGAL_TRAP)
        analysis = analyse_game(engine, game, scan_depth=10, deep_depth=14)
        profonde = [m for m in analysis.moves if m.depth == 14]
        assert len(profonde) == analysis.deep_positions

    def test_calcola_i_rapporti_per_colore(self, engine: Engine) -> None:
        game = parse_pgn(LEGAL_TRAP)
        analysis = analyse_game(engine, game, scan_depth=8, deep_depth=10)

        bianco = analysis.report(Color.WHITE)
        nero = analysis.report(Color.BLACK)

        assert bianco.moves > 0 and nero.moves > 0
        assert 0 <= bianco.accuracy <= 100
        assert 0 <= nero.accuracy <= 100
        # Il bianco vince con una trappola: deve risultare più preciso.
        assert bianco.accuracy > nero.accuracy

    def test_riferisce_l_avanzamento(self, engine: Engine) -> None:
        game = parse_pgn(SHORT_PGN)
        passi: list[tuple[int, int]] = []
        analyse_game(
            engine,
            game,
            scan_depth=8,
            deep_depth=10,
            on_progress=lambda a, b: passi.append((a, b)),
        )
        assert passi[0] == (1, len(game))
        assert passi[-1] == (len(game), len(game))

    def test_la_mossa_che_da_matto_non_perde_nulla(self, engine: Engine) -> None:
        # La posizione dopo è terminale e il motore non la analizzerebbe:
        # dare matto è la mossa perfetta, non un errore da 100%.
        game = parse_pgn(SHORT_PGN)
        analysis = analyse_game(engine, game, scan_depth=8, deep_depth=10)
        ultima = analysis.moves[-1]
        assert ultima.position.san == "Qxf7#"
        assert ultima.win_percent_drop == pytest.approx(0.0, abs=1.0)
