"""
L'applicazione FastAPI.

L'analisi dura decine di secondi, quindi l'endpoint principale non
restituisce una risposta sola alla fine: manda un flusso di eventi
(server-sent events) con l'avanzamento e poi il risultato. Senza,
il browser resterebbe fermo su una pagina bianca e molti proxy
chiuderebbero la connessione prima della fine.
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .schemas import analysis_json, game_json, player_json
from .service import AnalysisService, ServiceError

service = AnalysisService()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Il processo di Stockfish va chiuso, altrimenti resta orfano.
    service.shutdown()


app = FastAPI(title="chessreview", lifespan=lifespan)

# Durante lo sviluppo il frontend gira su una porta diversa.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(event: str, data: Any) -> str:
    """Un evento nel formato server-sent events."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "engine": service.engine_available}


@app.get("/api/games")
def games(
    username: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Le ultime partite di un giocatore."""
    try:
        found = service.list_games(username, limit)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "username": username,
        "games": [game_json(g, username) for g in found],
    }


@app.get("/api/player/{username}")
def player(username: str) -> dict[str, Any]:
    """Profilo pubblico e rating di un giocatore."""
    try:
        profile = service.get_player(username)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return player_json(profile)


@app.get("/api/analysis/{game_id}")
def cached(game_id: str, username: str | None = None) -> dict[str, Any]:
    """L'analisi se già presente in cache, altrimenti 404."""
    analysis = service.cached_analysis(game_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Non ancora analizzata")

    try:
        game = service.get_game(game_id)
    except ServiceError:
        game = None
    return analysis_json(analysis, game, username)


def _stream(game_id: str, username: str | None) -> Iterator[str]:
    """
    Esegue l'analisi in un thread e ne riporta l'avanzamento.

    L'analisi è sincrona e bloccante: girando nel thread della richiesta
    impedirebbe al server di rispondere ad altro. Il thread comunica
    attraverso una coda, che questo generatore svuota man mano.

    L'evento di errore si chiama "failure" e non "error": "error" è il
    nome dell'evento nativo con cui EventSource segnala le disconnessioni,
    e usarlo anche per gli errori applicativi rende i due casi
    indistinguibili nel browser.
    """
    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def work() -> None:
        try:
            analysis = service.analyse(
                game_id,
                on_progress=lambda phase, done, total: events.put(
                    ("progress", {"phase": phase, "done": done, "total": total})
                ),
            )
            try:
                game = service.get_game(game_id)
            except ServiceError:
                game = None
            events.put(("result", analysis_json(analysis, game, username)))
        except ServiceError as exc:
            events.put(("failure", {"message": str(exc)}))
        except Exception as exc:  # noqa: BLE001 — l'errore va comunicato, non nascosto
            events.put(("failure", {"message": f"{type(exc).__name__}: {exc}"}))

    threading.Thread(target=work, daemon=True).start()

    while True:
        kind, payload = events.get()
        yield sse(kind, payload)
        if kind in ("result", "failure"):
            return


@app.get("/api/analyse/{game_id}")
def analyse(game_id: str, username: str | None = None) -> StreamingResponse:
    """Analizza una partita, riportando l'avanzamento via SSE."""
    return StreamingResponse(
        _stream(game_id, username),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Impedisce a un eventuale proxy di bufferizzare il flusso,
            # che vanificherebbe l'intero meccanismo.
            "X-Accel-Buffering": "no",
        },
    )


class PgnRequest(BaseModel):
    pgn: str


@app.post("/api/analyse-pgn")
def analyse_pgn(request: PgnRequest) -> dict[str, Any]:
    """Analizza un PGN incollato a mano. Bloccante: nessun avanzamento."""
    try:
        analysis = service.analyse_pgn(request.pgn)
    except ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return analysis_json(analysis, None)
