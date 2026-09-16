from __future__ import annotations

import chess
import pytest

from chessreview.models import Color
from chessreview.positions import (
    PgnError,
    material_balance,
    parse_clock,
    parse_pgn,
    piece_count,
)

from fixtures_data import SHORT_PGN

#: Matto del barbiere: quattro mosse bianche, tre nere.
SCHOLARS_MATE = SHORT_PGN

#: Partita minima senza tag né orologi.
BARE_PGN = "1. e4 e5 2. Nf3 Nc6 *"

#: Arrocco, cattura, promozione e sottopromozione, per i casi limite.
EDGE_PGN = (
    '[TimeControl "600"]\n\n'
    "1. e4 d5 2. exd5 Qxd5 3. Nc3 Qa5 4. d4 c6 5. Nf3 Bg4 6. Bf4 e6 "
    "7. h3 Bxf3 8. Qxf3 Bb4 9. Be2 Nd7 10. O-O *"
)


class TestOrologio:
    def test_legge_il_tempo_rimasto(self) -> None:
        assert parse_clock("{[%clk 0:03:00.5]}") == pytest.approx(180.5)

    def test_gestisce_le_ore(self) -> None:
        assert parse_clock("[%clk 1:30:00]") == pytest.approx(5400.0)

    def test_senza_commento_restituisce_none(self) -> None:
        assert parse_clock("") is None
        assert parse_clock("{buona mossa}") is None


class TestMateriale:
    def test_posizione_iniziale_in_parita(self) -> None:
        assert material_balance(chess.Board()) == 0

    def test_conta_i_pezzi_senza_i_re(self) -> None:
        assert piece_count(chess.Board()) == 30

    def test_e_relativo_a_chi_muove(self) -> None:
        # Bianco senza donna: tocca al bianco, quindi è in svantaggio.
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
        assert material_balance(board) == -9
        # Stessa posizione ma tocca al nero: il segno si inverte.
        board.turn = chess.BLACK
        assert material_balance(board) == 9


class TestParsing:
    def test_conta_le_semimosse(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        # 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7# = sette semimosse.
        assert len(game) == 7

    def test_alterna_i_colori(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        assert [p.turn for p in game.positions[:4]] == [
            Color.WHITE,
            Color.BLACK,
            Color.WHITE,
            Color.BLACK,
        ]

    def test_la_posizione_precede_la_mossa(self) -> None:
        # Al ply 0 la scacchiera è quella iniziale e la mossa è e4:
        # è il motore che deve vedere la posizione PRIMA della mossa.
        first = parse_pgn(SCHOLARS_MATE).positions[0]
        assert first.fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w")
        assert first.san == "e4"
        assert first.uci == "e2e4"

    def test_numeri_di_mossa(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        assert [p.move_number for p in game.positions] == [1, 1, 2, 2, 3, 3, 4]

    def test_riconosce_scacchi_e_catture(self) -> None:
        last = parse_pgn(SCHOLARS_MATE).positions[-1]
        assert last.san == "Qxf7#"
        assert last.gives_check
        assert last.is_capture

    def test_filtra_per_colore(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        assert len(game.by_color(Color.WHITE)) == 4
        assert len(game.by_color(Color.BLACK)) == 3

    def test_regge_arrocchi_e_catture(self) -> None:
        game = parse_pgn(EDGE_PGN)
        sans = [p.san for p in game.positions]
        assert "O-O" in sans
        assert "Bxf3" in sans

    def test_funziona_senza_tag(self) -> None:
        game = parse_pgn(BARE_PGN)
        assert len(game) == 4
        assert all(p.clock_after is None for p in game.positions)
        assert all(p.time_spent is None for p in game.positions)

    def test_pgn_senza_mosse(self) -> None:
        with pytest.raises(PgnError):
            parse_pgn('[Event "vuoto"]\n\n*')

    def test_pgn_illeggibile(self) -> None:
        with pytest.raises(PgnError):
            parse_pgn("")


class TestTempoSpeso:
    def test_calcola_il_tempo_di_riflessione(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        # Bianco parte da 180s con incremento 2: dopo e4 ha 180.5,
        # quindi ha pensato 180 + 2 - 180.5 = 1.5 secondi.
        assert game.positions[0].time_spent == pytest.approx(1.5)

    def test_confronta_ogni_giocatore_con_se_stesso(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        # Il nero al ply 1: da 180 a 180.2, incremento 2 → 1.8 secondi.
        assert game.positions[1].time_spent == pytest.approx(1.8)
        # Il bianco al ply 2: da 180.5 a 181.9 → 0.6 secondi.
        assert game.positions[2].time_spent == pytest.approx(0.6)

    def test_non_produce_tempi_negativi(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        spent = [p.time_spent for p in game.positions]
        assert all(s is not None and s >= 0 for s in spent)

    def test_registra_anche_il_tempo_rimasto(self) -> None:
        game = parse_pgn(SCHOLARS_MATE)
        assert game.positions[0].clock_after == pytest.approx(180.5)
