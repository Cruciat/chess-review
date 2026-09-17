"""
Stato condiviso del servizio: il motore, le partite scaricate,
le analisi già fatte e quelle in corso.

Il motore è un processo unico e il protocollo UCI non è concorrente:
due richieste in parallelo sullo stesso processo corromperebbero il
dialogo. Un lock serializza gli accessi. È accettabile perché il
servizio è a uso personale: una persona analizza una partita alla volta.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from ..analysis import GameAnalysis, Phase, ProgressCallback, analyse_game
from ..chesscom import ChessComClient, PlayerNotFound
from ..engine import Engine, find_stockfish
from ..models import ImportedGame, PlayerProfile
from ..positions import PgnError, parse_pgn

USER_AGENT = "chessreview/0.1 (self-hosted)"

#: Partite troppo corte non hanno niente da analizzare: sono rese
#: immediate o abbandoni. Analizzarle produrrebbe statistiche prive
#: di senso su due o tre mosse.
MIN_PLIES = 10


class ServiceError(RuntimeError):
    """Errore che il servizio traduce in una risposta HTTP."""


@dataclass
class _Job:
    """
    Un'analisi in corso, a cui più richieste possono agganciarsi.

    Senza, una seconda richiesta per la stessa partita (una pagina
    ricaricata, o React che in sviluppo monta i componenti due volte)
    resterebbe ferma sul lock del motore senza avanzamento, per poi
    rifare da capo un'analisi appena conclusa.
    """

    listeners: list[ProgressCallback] = field(default_factory=list)
    #: L'ultimo avanzamento, per chi si aggancia a metà.
    last: tuple[Phase, int, int] | None = None
    done: threading.Event = field(default_factory=threading.Event)
    result: GameAnalysis | None = None
    error: BaseException | None = None


class AnalysisService:
    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._engine_lock = threading.Lock()

        #: Partite scaricate, per id (vedi ImportedGame.id). Evita di
        #: richiamare chess.com fra la lista e l'analisi.
        self._games: dict[str, ImportedGame] = {}

        #: Analisi già fatte, per id. Riaprire una partita già
        #: analizzata deve essere istantaneo: è la persistenza minima,
        #: in memoria finché non decideremo dove scriverla.
        self._analyses: dict[str, GameAnalysis] = {}

        #: Analisi in corso, per id. Protetto da _jobs_lock, che è
        #: distinto dal lock del motore: registrarsi a un'analisi non
        #: deve aspettare che il motore si liberi.
        self._jobs: dict[str, _Job] = {}
        self._jobs_lock = threading.Lock()

        #: chess.com chiede richieste in serie. Ogni chiamata crea il suo
        #: client, quindi il throttle del client non basta: l'elenco partite
        #: e il profilo, chiesti insieme dall'interfaccia, passano da qui.
        self._chesscom_lock = threading.Lock()

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
            with self._chesscom_lock, ChessComClient(USER_AGENT) as client:
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
            self._games[game.id] = game
        return games

    def get_player(self, username: str) -> PlayerProfile:
        """Profilo pubblico e rating di un giocatore."""
        try:
            with self._chesscom_lock, ChessComClient(USER_AGENT) as client:
                return client.fetch_profile(username)
        except PlayerNotFound as exc:
            raise ServiceError(str(exc)) from exc

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
        on_progress: ProgressCallback | None = None,
    ) -> GameAnalysis:
        """
        Analizza una partita, riusando il risultato se già disponibile.

        Se la stessa partita è già in analisi, la chiamata si aggancia a
        quella: riceve l'avanzamento da lì in poi e lo stesso risultato,
        senza occupare il motore una seconda volta.
        """
        with self._jobs_lock:
            cached = self._analyses.get(game_id)
            if cached is not None:
                return cached

            job = self._jobs.get(game_id)
            owner = job is None
            if job is None:
                job = _Job()
                self._jobs[game_id] = job

            if on_progress is not None:
                job.listeners.append(on_progress)
                if job.last is not None:
                    on_progress(*job.last)

        if not owner:
            job.done.wait()
            if job.error is not None:
                raise job.error
            assert job.result is not None
            return job.result

        def emit(phase: Phase, done: int, total: int) -> None:
            with self._jobs_lock:
                job.last = (phase, done, total)
                listeners = list(job.listeners)
            for listener in listeners:
                listener(phase, done, total)

        try:
            analysis = self._run(game_id, emit)
            job.result = analysis
            with self._jobs_lock:
                self._analyses[game_id] = analysis
            return analysis
        except BaseException as exc:
            job.error = exc
            raise
        finally:
            with self._jobs_lock:
                self._jobs.pop(game_id, None)
            job.done.set()

    def _run(self, game_id: str, on_progress: ProgressCallback) -> GameAnalysis:
        """Il lavoro vero di un'analisi, eseguito da chi l'ha avviata."""
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
            return analyse_game(engine, parsed, on_progress=on_progress)

    def analyse_pgn(
        self,
        pgn: str,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> GameAnalysis:
        """Analizza un PGN arbitrario, senza passare da chess.com."""
        try:
            parsed = parse_pgn(pgn)
        except PgnError as exc:
            raise ServiceError(f"PGN non analizzabile: {exc}") from exc

        with self._engine_lock:
            engine = self._get_engine()
            return analyse_game(engine, parsed, on_progress=on_progress)
