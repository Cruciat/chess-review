// Unico punto che parla con il backend. Gli URL sono relativi: in
// sviluppo li inoltra il proxy di Vite (vite.config.ts), in produzione
// basterà servire la UI dallo stesso host dell'API.

import type { Analysis, GameMeta, PlayerProfile, Progress } from './types';

const BACKEND_DOWN =
  'Il backend non risponde. Avvialo dalla radice del progetto con: uvicorn chessreview.api.app:app --reload';

export class ApiError extends Error {}

/** Il messaggio d'errore di FastAPI, se la risposta ne contiene uno. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail;
    }
  } catch {
    // Corpo non JSON: tipicamente è il proxy di Vite che non raggiunge il backend.
    return BACKEND_DOWN;
  }
  return `Il server ha risposto con un errore ${response.status}.`;
}

export async function fetchGames(
  username: string,
  { limit = 30, signal }: { limit?: number; signal?: AbortSignal } = {},
): Promise<GameMeta[]> {
  const query = new URLSearchParams({ username, limit: String(limit) });

  let response: Response;
  try {
    response = await fetch(`/api/games?${query}`, { signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(BACKEND_DOWN);
  }

  if (!response.ok) throw new ApiError(await errorMessage(response));
  const data = (await response.json()) as { games: GameMeta[] };
  return data.games;
}

/** Profilo e rating del giocatore. Null se non disponibile: è un di più, non blocca l'elenco. */
export async function fetchPlayer(username: string, { signal }: { signal?: AbortSignal } = {}): Promise<PlayerProfile | null> {
  try {
    const response = await fetch(`/api/player/${encodeURIComponent(username)}`, { signal });
    if (!response.ok) return null;
    return (await response.json()) as PlayerProfile;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    return null;
  }
}

export interface StreamHandlers {
  onProgress: (progress: Progress) => void;
  onResult: (analysis: Analysis) => void;
  onFailure: (message: string) => void;
}

/**
 * Avvia (o riaggancia) l'analisi di una partita e ne segue l'avanzamento.
 * Restituisce la funzione che chiude la connessione.
 *
 * L'errore applicativo arriva come evento "failure". L'evento nativo
 * "error" di EventSource scatta invece quando la connessione cade o non
 * si apre: lo si tratta come backend irraggiungibile, e si chiude subito
 * la connessione per evitare che il browser la riapra all'infinito.
 */
export function streamAnalysis(
  gameId: string,
  username: string | null,
  handlers: StreamHandlers,
): () => void {
  const query = username ? `?${new URLSearchParams({ username })}` : '';
  const source = new EventSource(`/api/analyse/${encodeURIComponent(gameId)}${query}`);
  let finished = false;

  const finish = () => {
    finished = true;
    source.close();
  };

  source.addEventListener('progress', (event) => {
    handlers.onProgress(JSON.parse((event as MessageEvent<string>).data) as Progress);
  });

  source.addEventListener('result', (event) => {
    finish();
    handlers.onResult(JSON.parse((event as MessageEvent<string>).data) as Analysis);
  });

  source.addEventListener('failure', (event) => {
    finish();
    const data = JSON.parse((event as MessageEvent<string>).data) as { message: string };
    handlers.onFailure(data.message);
  });

  source.onerror = () => {
    if (finished) return;
    finish();
    handlers.onFailure(BACKEND_DOWN);
  };

  return finish;
}
