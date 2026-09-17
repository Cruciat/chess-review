from __future__ import annotations

import json
from typing import Any, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from chessreview.api.app import app, service
from chessreview.api.schemas import fen_after, game_json, white_win_percent
from chessreview.chesscom import parse_game
from chessreview.engine import find_stockfish
from chessreview.models import Color, ImportedGame

from fixtures_data import game_payload

requires_engine = pytest.mark.skipif(
    find_stockfish() is None,
    reason="Stockfish non installato",
)

#: Partita abbastanza lunga da superare la soglia minima.
LEGAL_TRAP_PGN = (
    '[Event "Live Chess"]\n'
    '[White "Cruciat"]\n'
    '[Black "avversario"]\n'
    '[Result "1-0"]\n'
    '[TimeControl "180+2"]\n\n'
    "1. e4 e5 2. Nf3 Nc6 3. Bc4 d6 4. Nc3 Bg4 5. h3 Bh5 "
    "6. Nxe5 Bxd1 7. Bxf7+ Ke7 8. Nd5# 1-0"
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def sse_events(text: str) -> list[tuple[str, Any]]:
    """Spezza una risposta SSE in coppie (evento, dati)."""
    events: list[tuple[str, Any]] = []
    for block in text.strip().split("\n\n"):
        name = ""
        payload = ""
        for row in block.splitlines():
            if row.startswith("event: "):
                name = row[7:]
            elif row.startswith("data: "):
                payload = row[6:]
        if name:
            events.append((name, json.loads(payload)))
    return events


def inject(url: str) -> ImportedGame:
    """Mette una partita in cache saltando chess.com, e ne svuota l'analisi."""
    fake = parse_game(game_payload(pgn=LEGAL_TRAP_PGN, url=url))
    assert fake is not None
    service._games[fake.id] = fake
    service._analyses.pop(fake.id, None)
    return fake


class TestSerializzazione:
    def test_calcola_la_posizione_dopo_la_mossa(self) -> None:
        after = fen_after("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e4")
        assert after.startswith("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b")

    def test_metadati_della_partita(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        payload = game_json(game, "Cruciat")

        assert payload["yourColor"] == "white"
        assert payload["yourOutcome"] == "win"
        assert payload["eco"] == "C20"
        assert payload["timeClass"] == "blitz"

    def test_l_id_e_sicuro_per_un_percorso(self) -> None:
        game = parse_game(game_payload(url="https://www.chess.com/game/live/42"))
        assert game is not None
        assert game_json(game)["id"] == "live-42"

    def test_senza_username_non_indica_il_colore(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        payload = game_json(game)
        assert payload["yourColor"] is None


class TestEndpoint:
    def test_stato_del_servizio(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_giocatore_inesistente(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from chessreview.api import service as service_module

        def boom(*args: Any, **kwargs: Any) -> None:
            raise service_module.ServiceError("Giocatore non trovato")

        monkeypatch.setattr(service, "list_games", boom)
        assert client.get("/api/games?username=nessuno").status_code == 404

    def test_profilo_del_giocatore(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from chessreview.chesscom import parse_profile
        from fixtures_data import PROFILE_PAYLOAD, STATS_PAYLOAD

        monkeypatch.setattr(service, "get_player", lambda username: parse_profile(PROFILE_PAYLOAD, STATS_PAYLOAD))
        payload = client.get("/api/player/cruciat").json()

        assert payload["country"] == "IT"
        assert [r["timeClass"] for r in payload["ratings"]] == ["rapid", "blitz", "daily"]
        assert payload["ratings"][1]["rating"] == 948

    def test_profilo_inesistente(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from chessreview.api import service as service_module

        def boom(username: str) -> None:
            raise service_module.ServiceError("Giocatore non trovato")

        monkeypatch.setattr(service, "get_player", boom)
        assert client.get("/api/player/nessuno").status_code == 404

    def test_analisi_non_in_cache(self, client: TestClient) -> None:
        assert client.get("/api/analysis/inesistente").status_code == 404

    def test_username_obbligatorio(self, client: TestClient) -> None:
        assert client.get("/api/games").status_code == 422

    def test_partita_non_scaricata(self, client: TestClient) -> None:
        response = client.get("/api/analyse/mai-vista")
        events = sse_events(response.text)
        # "failure" e non "error", che in EventSource è l'evento nativo.
        assert events[-1][0] == "failure"


@requires_engine
class TestAnalisiVera:
    def test_analizza_un_pgn(self, client: TestClient) -> None:
        response = client.post("/api/analyse-pgn", json={"pgn": LEGAL_TRAP_PGN})
        assert response.status_code == 200

        payload = response.json()
        assert len(payload["moves"]) == 15
        assert payload["white"]["accuracy"] > payload["black"]["accuracy"]

    def test_ogni_mossa_ha_i_campi_attesi(self, client: TestClient) -> None:
        payload = client.post("/api/analyse-pgn", json={"pgn": LEGAL_TRAP_PGN}).json()
        move = payload["moves"][0]

        for key in ("san", "fenBefore", "fenAfter", "classification", "whiteWinPercent"):
            assert key in move

    def test_la_valutazione_e_dal_punto_di_vista_del_bianco(self, client: TestClient) -> None:
        # Il nero prende la donna e viene mattato: alla fine il bianco
        # deve stare vicino al 100%, non allo 0%.
        payload = client.post("/api/analyse-pgn", json={"pgn": LEGAL_TRAP_PGN}).json()
        assert payload["moves"][-1]["whiteWinPercent"] > 90

    def test_pgn_illeggibile(self, client: TestClient) -> None:
        response = client.post("/api/analyse-pgn", json={"pgn": "non sono un pgn"})
        assert response.status_code == 400

    def test_il_flusso_riporta_l_avanzamento(self, client: TestClient) -> None:
        fake = inject("https://www.chess.com/game/live/900001")

        response = client.get(f"/api/analyse/{fake.id}")
        events = sse_events(response.text)

        kinds = [name for name, _ in events]
        assert "progress" in kinds
        assert kinds[-1] == "result"

        primo = next(data for name, data in events if name == "progress")
        assert primo == {"phase": "scan", "done": 1, "total": 15}

    def test_la_seconda_richiesta_usa_la_cache(self, client: TestClient) -> None:
        fake = inject("https://www.chess.com/game/live/900002")

        client.get(f"/api/analyse/{fake.id}")
        cached = client.get(f"/api/analysis/{fake.id}")

        assert cached.status_code == 200
        assert len(cached.json()["moves"]) == 15

    def test_con_lo_username_il_risultato_indica_il_colore(self, client: TestClient) -> None:
        fake = inject("https://www.chess.com/game/live/900003")

        response = client.get(f"/api/analyse/{fake.id}?username=cruciat")
        risultato = next(data for name, data in sse_events(response.text) if name == "result")

        assert risultato["game"]["yourColor"] == "white"
        assert risultato["game"]["yourOutcome"] == "win"

    def test_il_risultato_include_la_posizione_iniziale(self, client: TestClient) -> None:
        payload = client.post("/api/analyse-pgn", json={"pgn": LEGAL_TRAP_PGN}).json()
        assert 40 <= payload["startWhiteWinPercent"] <= 65
