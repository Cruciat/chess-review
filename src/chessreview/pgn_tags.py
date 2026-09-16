"""
Lettura dei tag di intestazione di un PGN.

Chess.com mette nel JSON solo una parte dei metadati: apertura, modo
di conclusione e orario preciso stanno soltanto nei tag del PGN.
Questo modulo li estrae senza interpretare le mosse, che sono
competenza del passo successivo.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

#: [Nome "valore"] — una riga per tag, prima delle mosse.
_TAG = re.compile(r'^\[(\w+)\s+"([^"]*)"\]\s*$', re.MULTILINE)

#: "180+2" oppure "600" oppure "1/86400" per le partite daily.
_TIME_CONTROL = re.compile(r"^(\d+)(?:\+(\d+))?$")


def parse_tags(pgn: str) -> dict[str, str]:
    """Tutti i tag del PGN come dizionario."""
    return {name: value for name, value in _TAG.findall(pgn)}


def parse_time_control(raw: str) -> tuple[int, int] | None:
    """
    Secondi iniziali e incremento per mossa.
    Restituisce None per i formati che non sappiamo leggere,
    come le partite daily espresse in "1/86400".
    """
    match = _TIME_CONTROL.match(raw.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 0)


def parse_utc_datetime(date: str, time: str) -> datetime | None:
    """
    Combina i tag UTCDate e UTCTime, nel formato "2026.09.07" e "19:23:17".
    Più affidabile del timestamp del JSON, che indica solo la fine.
    """
    try:
        return datetime.strptime(f"{date} {time}", "%Y.%m.%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
