import { useEffect, useState } from 'react';
import { ApiError, fetchGames, fetchPlayer } from './api/client';
import type { GameMeta, PlayerProfile } from './api/types';
import GameList from './components/GameList';
import Landing from './components/Landing';
import PlayerCard from './components/PlayerCard';
import ReviewView from './components/ReviewView';

const USERNAME_KEY = 'chessreview:username';

type ListState =
  | { status: 'idle' }
  | { status: 'loading'; username: string }
  | { status: 'ready'; username: string; games: GameMeta[] }
  | { status: 'failed'; username: string; message: string };

function storedUsername(): string {
  try {
    return localStorage.getItem(USERNAME_KEY) ?? '';
  } catch {
    return '';
  }
}

export default function App() {
  const [draft, setDraft] = useState(storedUsername);
  const [request, setRequest] = useState<{ username: string; attempt: number } | null>(() => {
    const saved = storedUsername();
    return saved ? { username: saved, attempt: 0 } : null;
  });
  const [list, setList] = useState<ListState>(() => {
    const saved = storedUsername();
    return saved ? { status: 'loading', username: saved } : { status: 'idle' };
  });
  const [player, setPlayer] = useState<PlayerProfile | null>(null);
  const [selected, setSelected] = useState<GameMeta | null>(null);

  // Carica profilo ed elenco a ogni nuova richiesta; quella precedente, se ancora in volo, viene annullata.
  // Lo stato di caricamento lo imposta chi fa la richiesta (load, o lo stato iniziale).
  // Il profilo parte per primo: è più rapido, e così compare prima dell'elenco invece di spingerlo in basso.
  useEffect(() => {
    if (!request) return;
    const { username } = request;
    const controller = new AbortController();

    fetchPlayer(username, { signal: controller.signal })
      .then((profile) => setPlayer(profile))
      .catch(() => {
        // Annullata: la richiesta nuova porterà il suo profilo.
      });

    fetchGames(username, { signal: controller.signal })
      .then((games) => {
        setList({ status: 'ready', username, games });
        try {
          localStorage.setItem(USERNAME_KEY, username);
        } catch {
          // Senza localStorage si perde solo la comodità di ritrovare lo username.
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : 'Errore imprevisto nel caricare le partite.';
        setList({ status: 'failed', username, message });
      });

    return () => controller.abort();
  }, [request]);

  const load = (username: string) => {
    const clean = username.trim();
    if (!clean) return;
    setSelected(null);
    setPlayer(null);
    setList({ status: 'loading', username: clean });
    setRequest((previous) => ({ username: clean, attempt: (previous?.attempt ?? 0) + 1 }));
  };

  const listUsername = list.status === 'idle' ? null : list.username;
  const landing = list.status === 'idle' && !selected;

  return (
    <div className="mx-auto flex min-h-dvh max-w-[82rem] flex-col px-4 pb-16 sm:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-rule py-4">
        <button type="button" onClick={() => setSelected(null)} className="flex items-center gap-2.5 rounded-[3px] font-display text-2xl font-semibold">
          <img src="/favicon.svg" alt="" className="size-7" />
          chessreview
        </button>

        {/* Prima dello username il campo sta al centro della pagina; dopo, si sposta qui. */}
        {!landing && (
          <form
            className="flex w-full gap-2 sm:w-auto"
            onSubmit={(event) => {
              event.preventDefault();
              load(draft);
            }}
          >
            <label htmlFor="username" className="sr-only">
              Username di chess.com
            </label>
            <input
              id="username"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Username di chess.com"
              autoComplete="username"
              spellCheck={false}
              className="min-w-0 flex-1 rounded-[3px] border border-rule bg-well px-3 py-2 placeholder:text-muted/70 focus:border-muted focus:outline-none sm:w-64"
            />
            <button type="submit" className="shrink-0 rounded-[3px] bg-paper px-4 py-2 font-medium text-ink hover:bg-white disabled:opacity-50" disabled={!draft.trim()}>
              Carica partite
            </button>
          </form>
        )}
      </header>

      <main className="flex-1 pt-6">
        {selected ? (
          <ReviewView key={selected.id} game={selected} username={listUsername} onBack={() => setSelected(null)} />
        ) : list.status === 'idle' ? (
          <Landing draft={draft} onDraftChange={setDraft} onSubmit={() => load(draft)} />
        ) : (
          <ListScreen list={list} player={player} onOpen={setSelected} onRetry={() => request && load(request.username)} />
        )}
      </main>
    </div>
  );
}

interface ListScreenProps {
  list: Exclude<ListState, { status: 'idle' }>;
  player: PlayerProfile | null;
  onOpen: (game: GameMeta) => void;
  onRetry: () => void;
}

function ListScreen({ list, player, onOpen, onRetry }: ListScreenProps) {
  const games = list.status === 'ready' ? list.games : [];
  const card = player && player.username.toLowerCase() === list.username.toLowerCase() ? player : null;

  return (
    <div>
      {card && <PlayerCard profile={card} games={games} />}

      {list.status === 'loading' && <p className="py-8 text-muted">Carico le partite di {list.username}…</p>}

      {list.status === 'failed' && (
        <section role="alert" className="max-w-xl py-8">
          <p className="font-medium">Non riesco a caricare le partite di {list.username}</p>
          <p className="mt-1 text-muted">{list.message}</p>
          <button type="button" onClick={onRetry} className="mt-4 rounded-[3px] bg-paper px-4 py-2 font-medium text-ink hover:bg-white">
            Riprova
          </button>
        </section>
      )}

      {list.status === 'ready' && (
        <div>
          {card ? (
            <h2 className="mb-5 font-display text-2xl font-semibold">Ultime partite</h2>
          ) : (
            <h1 className="mb-5 font-display text-3xl font-semibold">Ultime partite di {list.username}</h1>
          )}
          {list.games.length > 0 ? (
            <GameList games={list.games} onOpen={onOpen} />
          ) : (
            <p className="text-muted">Nessuna partita pubblica trovata per {list.username}.</p>
          )}
        </div>
      )}
    </div>
  );
}
