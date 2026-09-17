from __future__ import annotations

from typing import Any

import httpx
import pytest

from chessreview.chesscom import (
    ChessComClient,
    ChessComError,
    PlayerNotFound,
    parse_archives,
    parse_games,
    parse_profile,
    parse_stats,
)

from fixtures_data import ARCHIVES_PAYLOAD, PROFILE_PAYLOAD, STATS_PAYLOAD, game_payload

def client_with(handler: Any, **kwargs: Any) -> ChessComClient:
    """
    Client con trasporto simulato: i test non toccano la rete.
    min_interval a zero perché qui non stiamo verificando il throttle.
    """
    transport = httpx.MockTransport(handler)
    kwargs.setdefault("min_interval", 0.0)
    kwargs.setdefault("max_retries", 2)
    return ChessComClient(
        "chessreview/0.1 (test)",
        client=httpx.Client(transport=transport),
        **kwargs,
    )


class TestParsingArchivi:
    def test_estrae_anno_e_mese_dall_url(self) -> None:
        archives = parse_archives(ARCHIVES_PAYLOAD)
        assert [(a.year, a.month) for a in archives] == [(2025, 11), (2025, 12), (2026, 1)]

    def test_li_ordina_dal_piu_vecchio(self) -> None:
        archives = parse_archives(ARCHIVES_PAYLOAD)
        assert archives == sorted(archives, key=lambda a: (a.year, a.month))

    def test_ignora_url_malformati(self) -> None:
        payload = {"archives": ["https://api.chess.com/pub/player/x/games/rotto", 42, None]}
        assert parse_archives(payload) == []

    def test_regge_una_risposta_vuota(self) -> None:
        assert parse_archives({}) == []


class TestParsingPartite:
    def test_ordina_dalla_piu_vecchia(self, games_payload: dict[str, Any]) -> None:
        games = parse_games(games_payload)
        assert [g.url for g in games] == [".../1", ".../2", ".../3"]

    def test_scarta_le_partite_senza_pgn(self) -> None:
        payload = {"games": [game_payload(pgn=None), game_payload(pgn="   "), game_payload()]}
        assert len(parse_games(payload)) == 1

    def test_converte_il_timestamp_in_data(self, games_payload: dict[str, Any]) -> None:
        game = parse_games(games_payload)[0]
        assert game.end_time.year == 2025
        assert game.end_time.tzinfo is not None

    def test_regge_campi_mancanti(self) -> None:
        minimo = {"pgn": "1. e4 e5 *"}
        game = parse_games({"games": [minimo]})[0]
        assert game.white.username == ""
        assert game.white.rating is None
        assert game.rules == "chess"


class TestClient:
    def test_manda_lo_user_agent(self) -> None:
        visto: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            visto.append(request.headers.get("User-Agent", ""))
            return httpx.Response(200, json=ARCHIVES_PAYLOAD)

        with client_with(handler) as client:
            client.list_archives("cruciat")

        assert visto == ["chessreview/0.1 (test)"]

    def test_rifiuta_uno_user_agent_vuoto(self) -> None:
        with pytest.raises(ValueError):
            ChessComClient("   ")

    def test_mette_lo_username_in_minuscolo(self) -> None:
        percorsi: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            percorsi.append(request.url.path)
            return httpx.Response(200, json=ARCHIVES_PAYLOAD)

        with client_with(handler) as client:
            client.list_archives("  CruciaT  ")

        assert percorsi == ["/pub/player/cruciat/games/archives"]

    def test_formatta_il_mese_con_due_cifre(self) -> None:
        percorsi: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            percorsi.append(request.url.path)
            return httpx.Response(200, json={"games": []})

        with client_with(handler) as client:
            client.fetch_month("cruciat", 2026, 3)

        assert percorsi == ["/pub/player/cruciat/games/2026/03"]

    def test_utente_inesistente(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with client_with(handler) as client:
            with pytest.raises(PlayerNotFound):
                client.list_archives("nessuno")

    def test_mese_vuoto_non_e_un_errore(self) -> None:
        # Chess.com risponde 404 anche per un mese senza partite:
        # è normale scorrendo gli archivi e non va confuso con
        # un giocatore inesistente.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with client_with(handler) as client:
            assert client.fetch_month("cruciatt", 2020, 1) == []

    def test_riprova_dopo_un_429(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("chessreview.chesscom.time.sleep", lambda _: None)
        chiamate = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            chiamate["n"] += 1
            if chiamate["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "1"})
            return httpx.Response(200, json=ARCHIVES_PAYLOAD)

        with client_with(handler) as client:
            archives = client.list_archives("cruciat")

        assert chiamate["n"] == 2
        assert len(archives) == 3

    def test_si_arrende_dopo_troppi_tentativi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("chessreview.chesscom.time.sleep", lambda _: None)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        with client_with(handler) as client:
            with pytest.raises(ChessComError):
                client.list_archives("cruciat")

    def test_scorre_le_partite_dalla_piu_recente(self, games_payload: dict[str, Any]) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/archives"):
                return httpx.Response(200, json=ARCHIVES_PAYLOAD)
            return httpx.Response(200, json=games_payload)

        with client_with(handler) as client:
            games = list(client.iter_games("cruciat"))

        # Tre mesi da tre partite ciascuno, dalla più recente.
        assert len(games) == 9
        assert games[0].url == ".../3"

    def test_il_generatore_si_ferma_quando_smetti_di_leggere(
        self, games_payload: dict[str, Any]
    ) -> None:
        richieste: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            richieste.append(request.url.path)
            if request.url.path.endswith("/archives"):
                return httpx.Response(200, json=ARCHIVES_PAYLOAD)
            return httpx.Response(200, json=games_payload)

        with client_with(handler) as client:
            primo = next(client.iter_games("cruciat"))

        assert primo is not None
        # Archivi più un solo mese: gli altri due non sono stati scaricati.
        assert len(richieste) == 2


class TestThrottle:
    def test_aspetta_fra_una_richiesta_e_l_altra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attese: list[float] = []
        monkeypatch.setattr("chessreview.chesscom.time.sleep", attese.append)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"games": []})

        with client_with(handler, min_interval=5.0) as client:
            client.fetch_month("cruciat", 2026, 1)
            client.fetch_month("cruciat", 2026, 2)

        # La prima richiesta parte subito, la seconda attende.
        assert len(attese) == 1
        assert 0 < attese[0] <= 5.0


class TestProfilo:
    def test_legge_il_profilo(self) -> None:
        profile = parse_profile(PROFILE_PAYLOAD, STATS_PAYLOAD)
        assert profile.username == "cruciat"
        assert profile.country == "IT"
        assert profile.league == "Legend"
        assert profile.joined is not None and profile.joined.year == 2017

    def test_i_rating_seguono_l_ordine_di_chess_com(self) -> None:
        # Nella risposta daily viene prima, ma si mostra per ultima.
        stats = parse_stats(STATS_PAYLOAD)
        assert [s.time_class for s in stats] == ["rapid", "blitz", "daily"]

    def test_le_cadenze_mai_giocate_mancano(self) -> None:
        assert all(s.time_class != "bullet" for s in parse_stats(STATS_PAYLOAD))

    def test_legge_rating_migliore_e_record(self) -> None:
        blitz = next(s for s in parse_stats(STATS_PAYLOAD) if s.time_class == "blitz")
        assert (blitz.rating, blitz.best) == (948, 1012)
        assert (blitz.wins, blitz.losses, blitz.draws) == (800, 790, 40)
        assert blitz.games == 1630

    def test_regge_campi_mancanti(self) -> None:
        profile = parse_profile({"username": "x", "country": 42}, {"chess_blitz": {"last": "rotto"}})
        assert profile.country is None
        assert profile.avatar is None
        assert profile.ratings[0].rating is None
        assert profile.ratings[0].games == 0

    def test_il_client_chiede_profilo_e_statistiche(self) -> None:
        percorsi: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            percorsi.append(request.url.path)
            if request.url.path.endswith("/stats"):
                return httpx.Response(200, json=STATS_PAYLOAD)
            return httpx.Response(200, json=PROFILE_PAYLOAD)

        with client_with(handler) as client:
            profile = client.fetch_profile("Cruciat")

        assert percorsi == ["/pub/player/cruciat", "/pub/player/cruciat/stats"]
        assert len(profile.ratings) == 3

    def test_senza_statistiche_restituisce_il_profilo(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/stats"):
                return httpx.Response(500)
            return httpx.Response(200, json=PROFILE_PAYLOAD)

        with client_with(handler, max_retries=0) as client:
            profile = client.fetch_profile("cruciat")

        assert profile.username == "cruciat"
        assert profile.ratings == ()

    def test_giocatore_inesistente(self) -> None:
        with client_with(lambda request: httpx.Response(404)) as client:
            with pytest.raises(PlayerNotFound):
                client.fetch_profile("nessuno")
