from __future__ import annotations

import pytest

from chessreview.pgn_tags import parse_tags, parse_time_control, parse_utc_datetime

from fixtures_data import SHORT_PGN


class TestTag:
    def test_legge_tutti_i_tag(self) -> None:
        tags = parse_tags(SHORT_PGN)
        assert tags["White"] == "Cruciat"
        assert tags["ECO"] == "C20"
        assert tags["Termination"] == "Cruciat won by checkmate"

    def test_regge_i_valori_vuoti(self) -> None:
        assert parse_tags('[Round ""]\n\n1. e4 *') == {"Round": ""}

    def test_ignora_le_mosse(self) -> None:
        tags = parse_tags(SHORT_PGN)
        assert "e4" not in tags
        assert all(not k.isdigit() for k in tags)

    def test_su_un_pgn_senza_tag_non_inventa_nulla(self) -> None:
        assert parse_tags("1. e4 e5 *") == {}


class TestControlloDiTempo:
    def test_con_incremento(self) -> None:
        assert parse_time_control("180+2") == (180, 2)

    def test_senza_incremento(self) -> None:
        assert parse_time_control("600") == (600, 0)

    def test_formato_daily_non_supportato(self) -> None:
        assert parse_time_control("1/86400") is None

    @pytest.mark.parametrize("raw", ["", "boh", "180+"])
    def test_formati_invalidi(self, raw: str) -> None:
        assert parse_time_control(raw) is None


class TestData:
    def test_combina_data_e_ora(self) -> None:
        parsed = parse_utc_datetime("2026.09.07", "19:23:17")
        assert parsed is not None
        assert (parsed.year, parsed.month, parsed.day, parsed.hour) == (2026, 9, 7, 19)
        assert parsed.tzinfo is not None

    def test_formato_invalido(self) -> None:
        assert parse_utc_datetime("07/09/2026", "19:23") is None
