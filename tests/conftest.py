"""
Fixture condivise fra i moduli di test.

I dati di esempio stanno in fixtures_data.py: questo file contiene
solo fixture, che pytest rende disponibili senza bisogno di importarle.
"""

from __future__ import annotations

from typing import Any

import pytest

from fixtures_data import game_payload


@pytest.fixture
def games_payload() -> dict[str, Any]:
    return {
        "games": [
            game_payload(url=".../3", end_time=1_760_000_300),
            game_payload(url=".../1", end_time=1_760_000_100),
            game_payload(url=".../2", end_time=1_760_000_200),
        ]
    }
