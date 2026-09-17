from __future__ import annotations

import chess
import pytest

from chessreview.classification import (
    DEFAULT_THRESHOLDS,
    MoveClass,
    MoveContext,
    Thresholds,
    classify,
    is_trivial_recapture,
    material_sacrificed,
)
from chessreview.engine import Evaluation
from chessreview.scoring import win_percent


def context(
    *,
    fen: str = chess.STARTING_FEN,
    move: str = "e2e4",
    is_best: bool = False,
    is_opening: bool = False,
    drop: float = 0.0,
    before: float = 50.0,
    after: float | None = None,
    margin: float | None = None,
    legal: int = 20,
    eval_before: Evaluation | None = None,
    eval_after: Evaluation | None = None,
    previous_capture: str | None = None,
) -> MoveContext:
    return MoveContext(
        fen_before=fen,
        move_uci=move,
        is_best=is_best,
        is_opening=is_opening,
        win_percent_drop=drop,
        win_percent_before=before,
        win_percent_after=after if after is not None else before - drop,
        eval_before=eval_before or Evaluation(cp=0),
        eval_after=eval_after or Evaluation(cp=0),
        win_margin_over_second=margin,
        legal_move_count=legal,
        previous_capture_square=previous_capture,
    )


#: Posizione del tranello di Légal dopo 5...Bh5: il bianco può giocare
#: Nxe5, che dà via la donna se il nero prende con Bxd1.
LEGAL_FEN = "r2qkbnr/ppp2ppp/2np4/4p2b/2B1P3/2N2N1P/PPPP1PP1/R1BQK2R w KQkq - 4 6"

#: Bxf7+: alfiere su casella difesa dal re, sacrificio netto.
SAC_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


class TestSacrificio:
    def test_una_mossa_tranquilla_non_sacrifica(self) -> None:
        assert material_sacrificed(chess.STARTING_FEN, "e2e4") == 0

    def test_riconosce_un_alfiere_dato_via(self) -> None:
        # Bxf7+: prende un pedone ma l'alfiere cade, bilancio negativo.
        assert material_sacrificed(SAC_FEN, "c4f7") >= 2

    def test_una_cattura_pari_non_e_sacrificio(self) -> None:
        # Cambio di pedoni difesi: nessuno ci rimette.
        fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        assert material_sacrificed(fen, "e4d5") == 0

    def test_prendere_un_pezzo_indifeso_non_e_sacrificio(self) -> None:
        # Donna che cattura un pedone indifeso e non può essere ripresa.
        fen = "4k3/8/8/3p4/8/8/8/3QK3 w - - 0 1"
        assert material_sacrificed(fen, "d1d5") == 0

    def test_una_mossa_illegale_non_sacrifica_nulla(self) -> None:
        assert material_sacrificed(chess.STARTING_FEN, "e2e5") == 0


#: Dopo 1.e4 d5 2.exd5: il bianco ha appena catturato in d5.
AFTER_EXD5 = "rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"


class TestRicattura:
    def test_riconosce_una_ricattura(self) -> None:
        assert is_trivial_recapture(AFTER_EXD5, "d8d5", "d5")

    def test_una_mossa_tranquilla_non_lo_e(self) -> None:
        assert not is_trivial_recapture(chess.STARTING_FEN, "e2e4", None)

    def test_catturare_altrove_non_e_ricatturare(self) -> None:
        # Partita dell'Opera, 4.dxe5 Bxf3: il bianco ha catturato in e5,
        # il nero cattura in f3. Il contatore delle semimosse è a zero,
        # ed è proprio il caso che la vecchia euristica sbagliava.
        fen = "rn1qkbnr/ppp2ppp/3p4/4P3/4P1b1/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 4"
        assert not is_trivial_recapture(fen, "g4f3", "e5")

    def test_una_cattura_dopo_una_mossa_di_pedone_non_lo_e(self) -> None:
        # Anche una mossa di pedone azzera il contatore: senza la casella
        # della cattura precedente non c'è ricattura.
        fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        assert not is_trivial_recapture(fen, "e4d5", None)


class TestOrdineDeiControlli:
    """
    L'ordine è la parte fragile del classificatore: questi test
    verificano che le categorie specifiche non vengano assorbite
    da quelle generiche.
    """

    def test_l_apertura_vince_su_tutto(self) -> None:
        assert classify(context(is_opening=True, drop=90.0)) is MoveClass.BOOK

    def test_la_mossa_forzata_precede_il_giudizio(self) -> None:
        assert classify(context(legal=1, drop=50.0)) is MoveClass.FORCED

    def test_la_vittoria_mancata_precede_la_scala(self) -> None:
        klass = classify(context(before=95.0, after=20.0, drop=75.0))
        assert klass is MoveClass.MISSED_WIN

    def test_una_perdita_grande_senza_vittoria_e_un_blunder(self) -> None:
        klass = classify(context(before=55.0, after=10.0, drop=45.0))
        assert klass is MoveClass.BLUNDER


class TestScalaDellePerdite:
    def test_la_mossa_del_motore_e_la_migliore(self) -> None:
        assert classify(context(is_best=True, drop=0.0)) is MoveClass.BEST

    @pytest.mark.parametrize(
        "drop,expected",
        [
            (0.5, MoveClass.EXCELLENT),
            (1.9, MoveClass.EXCELLENT),
            (3.0, MoveClass.GOOD),
            (7.0, MoveClass.INACCURACY),
            (15.0, MoveClass.MISTAKE),
            (40.0, MoveClass.BLUNDER),
        ],
    )
    def test_le_fasce(self, drop: float, expected: MoveClass) -> None:
        assert classify(context(drop=drop)) is expected

    def test_le_soglie_sono_configurabili(self) -> None:
        severe = Thresholds(excellent=0.5, good=1.0, inaccuracy=2.0, mistake=5.0)
        assert classify(context(drop=3.0)) is MoveClass.GOOD
        assert classify(context(drop=3.0), severe) is MoveClass.MISTAKE


class TestMossaUnica:
    def test_riconosce_l_unica_mossa_che_tiene(self) -> None:
        klass = classify(context(is_best=True, margin=30.0, drop=0.0))
        assert klass is MoveClass.CRITICAL

    def test_non_lo_e_se_le_alternative_erano_equivalenti(self) -> None:
        klass = classify(context(is_best=True, margin=2.0, drop=0.0))
        assert klass is MoveClass.BEST

    def test_serve_un_margine_ampio(self) -> None:
        assert classify(context(is_best=True, margin=15.0, drop=0.0)) is MoveClass.BEST
        assert classify(context(is_best=True, margin=25.0, drop=0.0)) is MoveClass.CRITICAL

    def test_un_matto_con_alternative_vincenti_non_e_unico(self) -> None:
        # Matto in uno contro una seconda linea a +8: 100% contro circa 95%.
        # Col margine in centipawn il matto valeva 10000 e passava sempre.
        seconda = win_percent(Evaluation(cp=800))
        klass = classify(context(is_best=True, margin=100.0 - seconda, drop=0.0, before=100.0))
        assert klass is MoveClass.BEST

    def test_una_ricattura_ovvia_non_lo_e(self) -> None:
        klass = classify(
            context(
                fen=AFTER_EXD5,
                move="d8d5",
                is_best=True,
                margin=40.0,
                legal=25,
                previous_capture="d5",
            )
        )
        assert klass is MoveClass.BEST

    def test_una_cattura_unica_che_non_riprende_lo_e(self) -> None:
        # Stessa mossa, ma senza cattura precedente in d5: è una scelta vera.
        klass = classify(context(fen=AFTER_EXD5, move="d8d5", is_best=True, margin=40.0, legal=25))
        assert klass is MoveClass.CRITICAL

    def test_non_lo_e_se_non_l_hai_trovata(self) -> None:
        klass = classify(context(is_best=False, margin=30.0, drop=8.0))
        assert klass is MoveClass.INACCURACY


class TestMossaBrillante:
    def test_un_sacrificio_corretto_e_brillante(self) -> None:
        klass = classify(context(fen=SAC_FEN, move="c4f7", drop=0.5, before=55.0))
        assert klass is MoveClass.BRILLIANT

    def test_precede_la_categoria_migliore(self) -> None:
        # Senza il controllo prima della scala, questa sarebbe BEST
        # e la brillantezza non verrebbe mai riconosciuta.
        klass = classify(context(fen=SAC_FEN, move="c4f7", drop=0.0, before=55.0, is_best=True))
        assert klass is MoveClass.BRILLIANT

    def test_un_sacrificio_sbagliato_non_lo_e(self) -> None:
        klass = classify(context(fen=SAC_FEN, move="c4f7", drop=40.0, before=55.0))
        assert klass is MoveClass.BLUNDER

    def test_non_lo_e_se_la_posizione_era_gia_vinta(self) -> None:
        # A +9 dare via un alfiere non è un merito, è indifferente.
        klass = classify(context(fen=SAC_FEN, move="c4f7", drop=0.5, before=95.0))
        assert klass is not MoveClass.BRILLIANT

    def test_un_sacrificio_che_forza_il_matto_lo_e(self) -> None:
        # Partita dell'Opera, 16.Qb8+: dopo la mossa è matto in due, quindi
        # la posizione vale 100%, ma solo grazie al sacrificio. La migliore
        # alternativa lasciava il bianco intorno al 70%.
        ctx = context(fen=SAC_FEN, move="c4f7", is_best=True, drop=0.0, before=100.0, margin=30.0)
        assert classify(ctx) is MoveClass.BRILLIANT

    def test_non_lo_e_se_anche_le_alternative_vincevano(self) -> None:
        ctx = context(fen=SAC_FEN, move="c4f7", is_best=True, drop=0.0, before=100.0, margin=3.0)
        assert classify(ctx) is not MoveClass.BRILLIANT

    def test_una_mossa_senza_sacrificio_non_lo_e(self) -> None:
        klass = classify(context(move="e2e4", drop=0.0, is_best=True))
        assert klass is MoveClass.BEST

    def test_la_soglia_di_materiale_e_configurabile(self) -> None:
        generoso = Thresholds(sacrifice_material=1)
        severo = Thresholds(sacrifice_material=8)
        ctx = context(fen=SAC_FEN, move="c4f7", drop=0.5, before=55.0)
        assert classify(ctx, generoso) is MoveClass.BRILLIANT
        assert classify(ctx, severo) is not MoveClass.BRILLIANT


class TestCategorie:
    def test_gli_errori_sono_marcati(self) -> None:
        assert MoveClass.BLUNDER.is_mistake
        assert MoveClass.MISSED_WIN.is_mistake
        assert not MoveClass.GOOD.is_mistake
        assert not MoveClass.BOOK.is_mistake

    def test_le_notevoli_includono_i_meriti(self) -> None:
        assert MoveClass.BRILLIANT.is_notable
        assert MoveClass.CRITICAL.is_notable
        assert MoveClass.BLUNDER.is_notable
        assert not MoveClass.GOOD.is_notable

    def test_ogni_categoria_ha_un_etichetta(self) -> None:
        from chessreview.classification import LABELS

        for klass in MoveClass:
            assert klass in LABELS
