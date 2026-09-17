from __future__ import annotations

from datetime import datetime, timezone

import pytest

from chessreview.chesscom import parse_game
from chessreview.models import Archive, Color, Outcome, PlayerSide

from fixtures_data import game_payload


def side(result: str) -> PlayerSide:
    return PlayerSide(username="x", rating=1200, result=result)


class TestOutcome:
    def test_vittoria(self) -> None:
        assert side("win").outcome is Outcome.WIN

    @pytest.mark.parametrize(
        "result",
        ["agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"],
    )
    def test_patte(self, result: str) -> None:
        assert side(result).outcome is Outcome.DRAW

    @pytest.mark.parametrize("result", ["checkmated", "resigned", "timeout", "abandoned"])
    def test_sconfitte(self, result: str) -> None:
        assert side(result).outcome is Outcome.LOSS

    def test_risultato_sconosciuto_vale_sconfitta(self) -> None:
        # Se chess.com aggiunge un esito che non conosciamo, meglio
        # registrarlo come sconfitta che far esplodere l'import.
        assert side("qualcosa_di_nuovo").outcome is Outcome.LOSS


class TestArchive:
    def test_un_mese_passato_e_concluso(self) -> None:
        now = datetime(2026, 9, 15, tzinfo=timezone.utc)
        assert Archive(2026, 8, "u").is_complete(now)
        assert Archive(2025, 12, "u").is_complete(now)

    def test_il_mese_corrente_non_lo_e(self) -> None:
        now = datetime(2026, 9, 15, tzinfo=timezone.utc)
        assert not Archive(2026, 9, "u").is_complete(now)

    def test_ne_i_mesi_futuri(self) -> None:
        now = datetime(2026, 9, 15, tzinfo=timezone.utc)
        assert not Archive(2026, 10, "u").is_complete(now)


class TestPartita:
    def test_riconosce_il_colore_ignorando_le_maiuscole(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.color_of("cruciat") is Color.WHITE
        assert game.color_of("CRUCIAT") is Color.WHITE
        assert game.color_of("avversario") is Color.BLACK

    def test_restituisce_none_per_chi_non_ha_giocato(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.color_of("estraneo") is None
        assert game.outcome_for("estraneo") is None

    def test_esito_dal_punto_di_vista_di_un_giocatore(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.outcome_for("cruciat") is Outcome.WIN
        assert game.outcome_for("avversario") is Outcome.LOSS

    def test_identifica_l_avversario(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        opponent = game.opponent_of("cruciat")
        assert opponent is not None
        assert opponent.username == "avversario"

    def test_marca_le_varianti(self) -> None:
        normale = parse_game(game_payload())
        variante = parse_game(game_payload(rules="chess960"))
        assert normale is not None and variante is not None
        assert normale.is_standard
        assert not variante.is_standard

    def test_estrae_il_codice_eco_dai_tag(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.eco_code == "C20"

    def test_estrae_il_nome_dell_apertura(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.opening_name == "Kings Pawn Opening"

    def test_senza_tag_non_inventa_aperture(self) -> None:
        game = parse_game(game_payload(pgn="1. e4 e5 *"))
        assert game is not None
        assert game.eco_code is None
        assert game.opening_name is None

    def test_legge_il_controllo_di_tempo(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.clock == (180, 2)

    def test_legge_il_modo_di_conclusione(self) -> None:
        game = parse_game(game_payload())
        assert game is not None
        assert game.termination == "Cruciat won by checkmate"

    def test_prende_l_orario_di_inizio_dai_tag(self) -> None:
        # I tag UTCDate e UTCTime indicano l'inizio della partita,
        # mentre end_time del JSON indica la fine: sono due istanti
        # diversi e started_at deve preferire il primo.
        game = parse_game(game_payload())
        assert game is not None
        assert game.started_at == datetime(2026, 9, 7, 19, 23, 17, tzinfo=timezone.utc)

    def test_senza_tag_di_orario_ricade_sulla_fine(self) -> None:
        game = parse_game(game_payload(pgn="1. e4 e5 *"))
        assert game is not None
        assert game.started_at == game.end_time


class TestIdentificativo:
    def test_usa_tipo_e_numero_della_partita(self) -> None:
        game = parse_game(game_payload(url="https://www.chess.com/game/live/123456789"))
        assert game is not None
        assert game.id == "live-123456789"

    def test_distingue_le_partite_daily(self) -> None:
        game = parse_game(game_payload(url="https://www.chess.com/game/daily/123456789"))
        assert game is not None
        assert game.id == "daily-123456789"

    def test_riconosce_il_formato_vecchio(self) -> None:
        game = parse_game(game_payload(url="https://www.chess.com/live/game/2185936567"))
        assert game is not None
        assert game.id == "live-2185936567"

    def test_senza_url_riconoscibile_usa_l_uuid(self) -> None:
        game = parse_game(game_payload(url="qualcosa", uuid="abc-123"))
        assert game is not None
        assert game.id == "abc-123"

    def test_senza_uuid_resta_deterministico(self) -> None:
        a = parse_game(game_payload(url="qualcosa", uuid=None))
        b = parse_game(game_payload(url="qualcosa", uuid=None))
        assert a is not None and b is not None
        assert a.id == b.id
        assert "/" not in a.id and ":" not in a.id
