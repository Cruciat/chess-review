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



class TestAccuratezzaDellaPartita:
    @staticmethod
    def sequenza(drops: list[float], start: float = 50.0) -> tuple[list[float], list[float], list[bool]]:
        """Win% del bianco coerente con le perdite, mosse alternate a partire dal bianco."""
        white = [start]
        movers = []
        for i, drop in enumerate(drops):
            is_white = i % 2 == 0
            movers.append(is_white)
            white.append(white[-1] - drop if is_white else white[-1] + drop)
        return white, drops, movers

    def test_una_partita_perfetta_vale_cento(self) -> None:
        bianco, nero = game_accuracy(*self.sequenza([0.0] * 20))
        assert bianco == pytest.approx(100.0, abs=0.2)
        assert nero == pytest.approx(100.0, abs=0.2)

    def test_senza_mosse_vale_cento(self) -> None:
        assert game_accuracy([50.0], [], []) == (100.0, 100.0)

    def test_i_colori_sono_separati(self) -> None:
        # Un blunder del nero non tocca l'accuratezza del bianco.
        drops = [0.0] * 20
        drops[11] = 40.0
        bianco, nero = game_accuracy(*self.sequenza(drops))
        assert bianco == pytest.approx(100.0, abs=0.2)
        assert nero < 90.0

    def test_un_blunder_pesa_piu_che_nella_media_semplice(self) -> None:
        # È il motivo del metodo: nella media aritmetica dieci mosse
        # perfette annegano l'errore che ha deciso la partita.
        drops = [0.0] * 20
        drops[10] = 40.0
        bianco, _ = game_accuracy(*self.sequenza(drops))
        semplice = sum(move_accuracy(d) for d in drops[0::2]) / 10
        assert bianco < semplice - 5.0

    def test_piu_perdi_piu_scende(self) -> None:
        piccolo = [0.0] * 20
        piccolo[10] = 5.0
        grande = [0.0] * 20
        grande[10] = 40.0
        assert game_accuracy(*self.sequenza(grande))[0] < game_accuracy(*self.sequenza(piccolo))[0]

    def test_resta_nell_intervallo(self) -> None:
        for acc in game_accuracy(*self.sequenza([100.0, 0.0] * 10)):
            assert 0.0 <= acc <= 100.0

    def test_rifiuta_lunghezze_incoerenti(self) -> None:
        with pytest.raises(ValueError):
            game_accuracy([50.0, 50.0], [0.0, 0.0], [True, False])


class TestAcpl:
    def test_media_semplice(self) -> None:
        assert average_centipawn_loss([10, 20, 30]) == pytest.approx(20.0)

    def test_senza_mosse_vale_zero(self) -> None:
        assert average_centipawn_loss([]) == 0.0
