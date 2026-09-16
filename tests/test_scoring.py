from __future__ import annotations

import pytest

from chessreview.engine import Evaluation
from chessreview.scoring import (
    average_centipawn_loss,
    game_accuracy,
    move_accuracy,
    win_percent,
    win_percent_lost,
)


class TestProbabilitaDiVittoria:
    def test_posizione_pari_vale_cinquanta(self) -> None:
        assert win_percent(Evaluation(cp=0)) == pytest.approx(50.0)

    def test_e_simmetrica(self) -> None:
        assert win_percent(Evaluation(cp=200)) + win_percent(Evaluation(cp=-200)) == pytest.approx(
            100.0
        )

    def test_cresce_con_il_vantaggio(self) -> None:
        valori = [win_percent(Evaluation(cp=cp)) for cp in (-500, -100, 0, 100, 500)]
        assert valori == sorted(valori)

    def test_un_pedone_di_vantaggio_vale_circa_sessanta(self) -> None:
        assert 58.0 < win_percent(Evaluation(cp=100)) < 68.0

    def test_un_matto_e_una_certezza(self) -> None:
        assert win_percent(Evaluation(mate=5)) == 100.0
        assert win_percent(Evaluation(mate=-1)) == 0.0

    def test_resta_nell_intervallo(self) -> None:
        for cp in (-100_000, -3000, 0, 3000, 100_000):
            assert 0.0 <= win_percent(Evaluation(cp=cp)) <= 100.0


class TestPerditaDiProbabilita:
    """
    Entrambe le valutazioni arrivano già orientate su chi ha mosso:
    è il contratto della funzione, e i test lo verificano così com'è.
    """

    def test_posizione_invariata_non_perde_nulla(self) -> None:
        assert win_percent_lost(Evaluation(cp=100), Evaluation(cp=100)) == pytest.approx(0.0)

    def test_perdere_terreno_costa(self) -> None:
        # Da +1.00 a pari: hai buttato via il vantaggio.
        drop = win_percent_lost(Evaluation(cp=100), Evaluation(cp=0))
        assert 5.0 < drop < 20.0

    def test_un_blunder_perde_molto(self) -> None:
        # Da pari a -5.00.
        assert win_percent_lost(Evaluation(cp=0), Evaluation(cp=-500)) > 30.0

    def test_non_produce_guadagni(self) -> None:
        # Se la posizione migliora, la perdita è zero e non negativa.
        assert win_percent_lost(Evaluation(cp=0), Evaluation(cp=500)) == 0.0

    def test_perdere_un_matto_e_gravissimo(self) -> None:
        drop = win_percent_lost(Evaluation(mate=2), Evaluation(cp=0))
        assert drop == pytest.approx(50.0, abs=1.0)

    def test_regalare_il_matto_costa_tutto(self) -> None:
        assert win_percent_lost(Evaluation(cp=0), Evaluation(mate=-1)) == pytest.approx(50.0)

    def test_dare_matto_non_costa_nulla(self) -> None:
        assert win_percent_lost(Evaluation(mate=1), Evaluation(mate=1)) == 0.0

    def test_la_funzione_non_inverte_il_punto_di_vista(self) -> None:
        # Se invertisse, questa coppia darebbe circa 18 invece di zero.
        # È il bug che il contratto esiste per prevenire.
        assert win_percent_lost(Evaluation(cp=100), Evaluation(cp=100)) < 0.001


class TestAccuratezza:
    def test_nessuna_perdita_da_cento(self) -> None:
        assert move_accuracy(0.0) == pytest.approx(100.0, abs=0.1)

    def test_cala_al_crescere_della_perdita(self) -> None:
        valori = [move_accuracy(d) for d in (0, 5, 10, 25, 50)]
        assert valori == sorted(valori, reverse=True)

    def test_resta_nell_intervallo(self) -> None:
        for drop in (0.0, 1.0, 50.0, 100.0, 1000.0):
            assert 0.0 <= move_accuracy(drop) <= 100.0

    def test_media_sulla_partita(self) -> None:
        assert game_accuracy([0.0, 0.0, 0.0]) == pytest.approx(100.0, abs=0.1)
        assert game_accuracy([]) == 100.0
        assert game_accuracy([0.0, 40.0]) < game_accuracy([0.0, 5.0])


class TestAcpl:
    def test_media_semplice(self) -> None:
        assert average_centipawn_loss([10, 20, 30]) == pytest.approx(20.0)

    def test_senza_mosse_vale_zero(self) -> None:
        assert average_centipawn_loss([]) == 0.0
