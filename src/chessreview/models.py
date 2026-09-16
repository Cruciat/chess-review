"""
Modelli dei dati che arrivano da chess.com.

Sono dataclass semplici e non modelli di validazione: l'API è esterna
e i suoi campi possono cambiare senza preavviso, quindi il parsing è
scritto a mano ed è tollerante su ciò che non conosciamo. Meglio una
partita importata con un campo mancante che un import che esplode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .pgn_tags import parse_time_control

# Varianti: Stockfish le valuterebbe come scacchi normali,
# producendo giudizi senza senso. Vanno riconosciute e scartate.
STANDARD_RULES = "chess"

# Esiti che chess.com usa per la patta. Tutto ciò che non è
# "win" e non è in questo insieme è una sconfitta.
DRAW_RESULTS = frozenset(
    {
        "agreed",
        "repetition",
        "stalemate",
        "insufficient",
        "50move",
        "timevsinsufficient",
    }
)


class Color(str, Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opponent(self) -> Color:
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class Outcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


@dataclass(frozen=True)
class Archive:
    """Un mese di partite di un giocatore."""

    year: int
    month: int
    url: str

    def is_complete(self, now: datetime | None = None) -> bool:
        """
        Vero se il mese è concluso e quindi non cambierà più.
        È la proprietà che rende gli archivi passati cachabili per sempre.
        """
        ref = now or datetime.now(timezone.utc)
        return (self.year, self.month) < (ref.year, ref.month)

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"


@dataclass(frozen=True)
class PlayerSide:
    username: str
    rating: int | None
    #: Stringa grezza di chess.com: "win", "resigned", "timeout", ecc.
    result: str

    @property
    def outcome(self) -> Outcome:
        if self.result == "win":
            return Outcome.WIN
        if self.result in DRAW_RESULTS:
            return Outcome.DRAW
        return Outcome.LOSS


@dataclass(frozen=True)
class ImportedGame:
    """Una partita così come arriva da chess.com, prima di ogni analisi."""

    url: str
    pgn: str
    rules: str
    time_class: str
    time_control: str
    rated: bool
    end_time: datetime
    white: PlayerSide
    black: PlayerSide
    uuid: str | None = None
    initial_fen: str | None = None
    #: Tag di intestazione del PGN: è lì che stanno ECO, Termination e orari.
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def is_standard(self) -> bool:
        """Scacchi normali, non una variante."""
        return self.rules == STANDARD_RULES

    @property
    def eco_code(self) -> str | None:
        """Codice ECO dell'apertura, es. 'C45'. Viene dai tag del PGN."""
        code = self.tags.get("ECO")
        return code if code and len(code) == 3 and code[0].isalpha() else None

    @property
    def opening_name(self) -> str | None:
        """
        Nome dell'apertura, ricavato dallo slug di ECOUrl:
        'Scotch-Game-Scotch-Gambit' diventa 'Scotch Game Scotch Gambit'.
        """
        url = self.tags.get("ECOUrl")
        if not url:
            return None
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        # Lo slug comincia col codice ECO, che è già disponibile a parte.
        parts = slug.split("-")
        if parts and len(parts[0]) == 3 and parts[0][0].isalpha():
            parts = parts[1:]
        return " ".join(parts) or None

    @property
    def termination(self) -> str | None:
        """Come è finita: 'X won on time', 'X won by resignation', ecc."""
        return self.tags.get("Termination")

    @property
    def clock(self) -> tuple[int, int] | None:
        """Secondi iniziali e incremento, da '180+2'."""
        return parse_time_control(self.time_control)

    @property
    def started_at(self) -> datetime:
        """Inizio della partita se noto, altrimenti la fine."""
        from .pgn_tags import parse_utc_datetime

        date = self.tags.get("UTCDate")
        time = self.tags.get("UTCTime")
        if date and time:
            parsed = parse_utc_datetime(date, time)
            if parsed is not None:
                return parsed
        return self.end_time

    def side(self, color: Color) -> PlayerSide:
        return self.white if color is Color.WHITE else self.black

    def color_of(self, username: str) -> Color | None:
        """Con che colore ha giocato un dato utente, se ha giocato."""
        target = username.strip().lower()
        if self.white.username.lower() == target:
            return Color.WHITE
        if self.black.username.lower() == target:
            return Color.BLACK
        return None

    def outcome_for(self, username: str) -> Outcome | None:
        color = self.color_of(username)
        return self.side(color).outcome if color else None

    def opponent_of(self, username: str) -> PlayerSide | None:
        color = self.color_of(username)
        return self.side(color.opponent) if color else None
