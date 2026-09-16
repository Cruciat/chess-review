"""
Client per la Published-Data API di chess.com.

È una REST API pubblica e in sola lettura: nessun account, nessuna chiave.
Chess.com chiede però esplicitamente di non parallelizzare le richieste e
di mandare uno User-Agent che permetta di contattare chi sviluppa, quindi
il client serializza e si identifica.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Iterator, Sequence

import httpx

from .models import Archive, ImportedGame, PlayerSide
from .pgn_tags import parse_tags

BASE_URL = "https://api.chess.com/pub"

#: Gli URL degli archivi finiscono con /YYYY/MM.
_ARCHIVE_URL = re.compile(r"/(\d{4})/(\d{2})/?$")


class ChessComError(RuntimeError):
    """Errore generico nel dialogo con l'API."""


class PlayerNotFound(ChessComError):
    def __init__(self, username: str) -> None:
        super().__init__(
            f"Giocatore '{username}' non trovato su chess.com. "
            f"Controlla su https://www.chess.com/member/{username}"
        )
        self.username = username


class ArchiveNotFound(ChessComError):
    """
    Mese senza partite. Chess.com risponde 404 anche in questo caso,
    che è diverso da "il giocatore non esiste": distinguerli evita
    messaggi fuorvianti quando si scorrono molti mesi.
    """

    def __init__(self, username: str, year: int, month: int) -> None:
        super().__init__(f"Nessuna partita per '{username}' in {year}-{month:02d}")
        self.username = username
        self.year = year
        self.month = month

class _NotFound(ChessComError):
    """Segnale interno: il 404 va tradotto da chi ha fatto la richiesta."""

# ---------------------------------------------------------------------------
# Parsing: funzioni pure, nessuna rete, testabili da sole
# ---------------------------------------------------------------------------


def parse_archives(payload: dict[str, Any]) -> list[Archive]:
    """
    Estrae gli archivi mensili dalla risposta dell'endpoint /archives.
    L'anno e il mese si leggono dall'URL stesso, che è l'unica cosa
    che quella risposta contiene.
    """
    archives: list[Archive] = []
    for url in payload.get("archives", []):
        if not isinstance(url, str):
            continue
        match = _ARCHIVE_URL.search(url)
        if not match:
            continue
        archives.append(Archive(year=int(match.group(1)), month=int(match.group(2)), url=url))

    archives.sort(key=lambda a: (a.year, a.month))
    return archives


def _parse_side(raw: Any) -> PlayerSide:
    data = raw if isinstance(raw, dict) else {}
    rating = data.get("rating")
    return PlayerSide(
        username=str(data.get("username", "")),
        rating=int(rating) if isinstance(rating, (int, float)) else None,
        result=str(data.get("result", "")),
    )


def parse_game(raw: dict[str, Any]) -> ImportedGame | None:
    """
    Converte una partita del JSON in ImportedGame.

    Restituisce None se manca il PGN: succede con le partite in corso
    e con quelle abbandonate prima della prima mossa, che non hanno
    nulla da analizzare.
    """
    pgn = raw.get("pgn")
    if not isinstance(pgn, str) or not pgn.strip():
        return None

    end = raw.get("end_time")
    end_time = (
        datetime.fromtimestamp(int(end), tz=timezone.utc)
        if isinstance(end, (int, float))
        else datetime.now(timezone.utc)
    )

    # Apertura, modo di conclusione e orari stanno solo qui dentro:
    # il JSON di chess.com non li espone come campi propri.
    tags = parse_tags(pgn)

    return ImportedGame(
        url=str(raw.get("url", "")),
        pgn=pgn,
        rules=str(raw.get("rules", "chess")),
        time_class=str(raw.get("time_class", "")),
        time_control=str(raw.get("time_control", "")),
        rated=bool(raw.get("rated", False)),
        end_time=end_time,
        white=_parse_side(raw.get("white")),
        black=_parse_side(raw.get("black")),
        uuid=raw.get("uuid") if isinstance(raw.get("uuid"), str) else None,
        initial_fen=raw.get("initial_setup") if isinstance(raw.get("initial_setup"), str) else None,
        tags=tags,
    )


def parse_games(payload: dict[str, Any]) -> list[ImportedGame]:
    """Tutte le partite di un archivio mensile, dalla più vecchia alla più recente."""
    games: list[ImportedGame] = []
    for raw in payload.get("games", []):
        if not isinstance(raw, dict):
            continue
        game = parse_game(raw)
        if game is not None:
            games.append(game)

    games.sort(key=lambda g: g.end_time)
    return games


# ---------------------------------------------------------------------------
# Client HTTP
# ---------------------------------------------------------------------------


class ChessComClient:
    """
    Richieste rigorosamente in serie, con un intervallo minimo fra l'una
    e l'altra. È una richiesta esplicita di chess.com: in parallelo
    vieni limitato, in serie no.
    """

    def __init__(
        self,
        user_agent: str,
        *,
        min_interval: float = 0.4,
        max_retries: int = 3,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError(
                "Serve uno User-Agent che ti identifichi: chess.com lo usa "
                "per contattarti invece di bloccarti se qualcosa va storto."
            )

        self.min_interval = min_interval
        self.max_retries = max_retries
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=True)
        self._client.headers["User-Agent"] = user_agent
        self._client.headers["Accept"] = "application/json"
        self._last_request: float | None = None

    # -- gestione della risorsa ------------------------------------------

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ChessComClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- meccanica delle richieste ---------------------------------------

    def _throttle(self) -> None:
        if self._last_request is None:
            return
        elapsed = time.monotonic() - self._last_request
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, path: str, *, username: str = "") -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:  # rete assente, timeout, ecc.
                last_error = exc
                time.sleep(2**attempt)
                continue
            finally:
                self._last_request = time.monotonic()

            if response.status_code == 404:
                # Chi chiama sa se stava cercando un giocatore o un mese,
                # e traduce il 404 nell'eccezione giusta.
                raise _NotFound(username or path)

            # 429 = troppe richieste, 5xx = problema loro: si riprova.
            if response.status_code == 429 or response.status_code >= 500:
                wait = _retry_after(response) or 2**attempt
                last_error = ChessComError(f"HTTP {response.status_code} su {url}")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                raise ChessComError(f"HTTP {response.status_code} su {url}")

            try:
                payload = response.json()
            except ValueError as exc:
                raise ChessComError(f"Risposta non JSON da {url}") from exc

            if not isinstance(payload, dict):
                raise ChessComError(f"Risposta inattesa da {url}")
            return payload

        raise ChessComError(f"Richiesta a {url} fallita dopo {self.max_retries} tentativi") from last_error

    # -- endpoint ---------------------------------------------------------

    def list_archives(self, username: str) -> list[Archive]:
        """Tutti i mesi in cui il giocatore ha partite, dal più vecchio."""
        user = _normalize(username)
        try:
            payload = self._get(f"/player/{user}/games/archives", username=user)
        except _NotFound:
            # Qui il 404 può voler dire una cosa sola.
            raise PlayerNotFound(user) from None
        return parse_archives(payload)

    def fetch_month(self, username: str, year: int, month: int) -> list[ImportedGame]:
        """
        Le partite di un singolo mese.
        Un mese senza partite restituisce una lista vuota, non un errore:
        è una situazione normale scorrendo gli archivi.
        """
        user = _normalize(username)
        try:
            payload = self._get(f"/player/{user}/games/{year}/{month:02d}", username=user)
        except _NotFound:
            return []
        return parse_games(payload)

    def fetch_archive(self, archive: Archive, username: str) -> list[ImportedGame]:
        return self.fetch_month(username, archive.year, archive.month)

    def iter_games(
        self,
        username: str,
        *,
        archives: Sequence[Archive] | None = None,
        newest_first: bool = True,
    ) -> Iterator[ImportedGame]:
        """
        Scorre le partite un mese alla volta.

        È un generatore di proposito: scaricare anni di partite richiede
        decine di richieste, e così chi chiama può fermarsi quando vuole
        senza aspettare la fine.
        """
        months = list(archives if archives is not None else self.list_archives(username))
        if newest_first:
            months.reverse()

        for archive in months:
            games = self.fetch_archive(archive, username)
            if newest_first:
                games.reverse()
            yield from games


def _normalize(username: str) -> str:
    """L'API vuole lo username in minuscolo nel percorso."""
    user = username.strip().lower()
    if not user:
        raise ValueError("Username vuoto")
    return user


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
