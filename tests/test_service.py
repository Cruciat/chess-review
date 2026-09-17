"""
Le analisi concorrenti della stessa partita.

Non serve Stockfish: analyse_game viene sostituita da una versione
finta e lenta, che riferisce l'avanzamento e conta le esecuzioni.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from chessreview.analysis import GameAnalysis, Phase
from chessreview.api import service as service_module
from chessreview.api.service import AnalysisService, ServiceError
from chessreview.chesscom import parse_game

from fixtures_data import game_payload

PGN = (
    '[TimeControl "180+2"]\n\n'
    "1. e4 e5 2. Nf3 Nc6 3. Bc4 d6 4. Nc3 Bg4 5. h3 Bh5 "
    "6. Nxe5 Bxd1 7. Bxf7+ Ke7 8. Nd5# 1-0"
)


@pytest.fixture
def svc(monkeypatch: pytest.MonkeyPatch) -> tuple[AnalysisService, list[int], threading.Event]:
    """Servizio con una partita in cache e un'analisi finta che attende un segnale."""
    service = AnalysisService()
    game = parse_game(game_payload(pgn=PGN, url="https://www.chess.com/game/live/7"))
    assert game is not None
    service._games[game.id] = game

    runs: list[int] = []
    release = threading.Event()
    sentinel = object()

    def fake_analyse_game(engine: Any, parsed: Any, *, on_progress: Any = None) -> Any:
        runs.append(1)
        on_progress("scan", 1, 2)
        release.wait(timeout=5)
        on_progress("scan", 2, 2)
        return sentinel

    monkeypatch.setattr(service_module, "analyse_game", fake_analyse_game)
    monkeypatch.setattr(service, "_get_engine", lambda: None)
    return service, runs, release


class TestAnalisiConcorrenti:
    def test_la_stessa_partita_si_analizza_una_volta(
        self, svc: tuple[AnalysisService, list[int], threading.Event]
    ) -> None:
        service, runs, release = svc
        results: list[GameAnalysis] = []

        def call() -> None:
            results.append(service.analyse("live-7"))

        threads = [threading.Thread(target=call) for _ in range(3)]
        for t in threads:
            t.start()
        time.sleep(0.2)
        release.set()
        for t in threads:
            t.join(timeout=5)

        assert len(runs) == 1
        assert len(results) == 3
        assert results[0] is results[1] is results[2]

    def test_chi_si_aggancia_riceve_l_ultimo_avanzamento(
        self, svc: tuple[AnalysisService, list[int], threading.Event]
    ) -> None:
        service, _, release = svc
        seen: list[tuple[Phase, int, int]] = []

        first = threading.Thread(target=lambda: service.analyse("live-7"))
        first.start()
        time.sleep(0.2)

        second = threading.Thread(
            target=lambda: service.analyse(
                "live-7", on_progress=lambda p, d, t: seen.append((p, d, t))
            )
        )
        second.start()
        time.sleep(0.2)
        release.set()
        first.join(timeout=5)
        second.join(timeout=5)

        # Il primo avanzamento era già passato: chi arriva dopo lo riceve
        # subito, e poi riceve il successivo come tutti.
        assert seen == [("scan", 1, 2), ("scan", 2, 2)]

    def test_finita_l_analisi_si_usa_la_cache(
        self, svc: tuple[AnalysisService, list[int], threading.Event]
    ) -> None:
        service, runs, release = svc
        release.set()
        first = service.analyse("live-7")
        second = service.analyse("live-7")
        assert first is second
        assert len(runs) == 1

    def test_l_errore_arriva_a_tutti_e_non_resta_in_sospeso(
        self, svc: tuple[AnalysisService, list[int], threading.Event]
    ) -> None:
        service, _, _ = svc
        with pytest.raises(ServiceError):
            service.analyse("inesistente")
        assert service._jobs == {}
