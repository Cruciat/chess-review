"""
Stato condiviso del servizio: il motore, le partite scaricate,
le analisi già fatte.

Il motore è un processo unico e il protocollo UCI non è concorrente:
due richieste in parallelo sullo stesso processo corromperebbero il
dialogo. Un lock serializza gli accessi. È accettabile perché il
servizio è a uso personale: una persona analizza una partita alla volta.
"""

from __future__ import annotations

import threading
from typing import Callable

from ..analysis import GameAnalysis, analyse_game
from ..chesscom import ChessComClient, PlayerNotFound
from ..engine import Engine, find_stockfish
from ..models import ImportedGame
from ..positions import PgnError, parse_pgn

USER_AGENT = "chessreview/0.1 (self-hosted)"

#: Partite troppo corte non hanno niente da analizzare: sono rese
#: immediate o abbandoni. Analizzarle produrrebbe statistiche prive
#: di senso su due o tre mosse.
MIN_PLIES = 10


class ServiceError(RuntimeError):
    """Errore che il servizio traduce in una risposta HTTP."""


class AnalysisService:
    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._engine_lock = threading.Lock()

        #: Partite scaricate, per URL. Evita di richiamare chess.com
        #: fra la lista e l'analisi.
        self._games: dict[str, ImportedGame] = {}

        #: Analisi già fatte, per URL. Riaprire una partita già
        #: analizzata deve essere istantaneo: è la persistenza minima,
        #: in memoria finché non decideremo dove scriverla.
        self._analyses: dict[str, GameAnalysis] = {}

    # -- motore ----------------------------------------------------------

    @property
    def engine_available(self) -> bool:
        return find_stockfish() is not None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            if not self.engine_available:
                raise ServiceError("Stockfish non trovato sul sistema")
            self._engine = Engine(threads=4, hash_mb=256)
        return self._engine

    def shutdown(self) -> None:
        if self._engine is not None:
            self._engine.close()
            self._engine = None

    # -- partite ---------------------------------------------------------

    def list_games(self, username: str, limit: int = 20) -> list[ImportedGame]:
        """Le ultime partite di un giocatore, dalla più recente."""
        try:
            with ChessComClient(USER_AGENT) as client:
                archives = client.list_archives(username)
                if not archives:
                    return []

                collected: list[ImportedGame] = []
                # Si risale un mese alla volta finché non ne bastano.
                for archive in reversed(archives):
                    collected = client.fetch_archive(archive, username) + collected
                    if len(collected) >= limit:
                        break
        except PlayerNotFound as exc:
            raise ServiceError(str(exc)) from exc

        games = list(reversed(collected))[:limit]
        for game in games:
            self._games[game.url] = game
        return games

    def get_game(self, game_id: str) -> ImportedGame:
        game = self._games.get(game_id)
        if game is None:
            raise ServiceError("Partita non in cache: rileggi prima l'elenco")
        return game

    # -- analisi ---------------------------------------------------------

    def cached_analysis(self, game_id: str) -> GameAnalysis | None:
        return self._analyses.get(game_id)

    def analyse(
        self,
        game_id: str,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> GameAnalysis:
        """
        Analizza una partita, riusando il risultato se già disponibile.

        L'intera operazione è sotto lock: il motore è un processo solo.
        """
        cached = self._analyses.get(game_id)
        if cached is not None:
            return cached

        game = self.get_game(game_id)
        if not game.is_standard:
            raise ServiceError(f"Variante non supportata: {game.rules}")

        try:
            parsed = parse_pgn(game.pgn)
        except PgnError as exc:
            raise ServiceError(f"PGN non analizzabile: {exc}") from exc

        if len(parsed) < MIN_PLIES:
            raise ServiceError(f"Partita troppo corta: {len(parsed)} semimosse")

        with self._engine_lock:
            engine = self._get_engine()
            analysis = analyse_game(engine, parsed, on_progress=on_progress)

        self._analyses[game_id] = analysis
        return analysis

    def analyse_pgn(
        self,
        pgn: str,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> GameAnalysis:
        """Analizza un PGN arbitrario, senza passare da chess.com."""
        try:
            parsed = parse_pgn(pgn)
        except PgnError as exc:
            raise ServiceError(f"PGN non analizzabile: {exc}") from exc

        with self._engine_lock:
            engine = self._get_engine()
            return analyse_game(engine, parsed, on_progress=on_progress)
