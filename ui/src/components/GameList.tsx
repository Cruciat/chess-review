import type { GameMeta } from '../api/types';
import { formatPlayedAt, formatTermination, formatTimeControl, outcomeLabel } from '../lib/format';

interface GameListProps {
  games: GameMeta[];
  onOpen: (game: GameMeta) => void;
}

/** Quadratino dell'esito: pieno se vinta, vuoto se persa, a metà se patta. */
function OutcomeMark({ outcome }: { outcome: GameMeta['yourOutcome'] }) {
  return (
    <svg viewBox="0 0 12 12" className="size-3 shrink-0" aria-hidden>
      <rect x="0.75" y="0.75" width="10.5" height="10.5" rx="1.5" className="stroke-paper" fill="none" strokeWidth="1.5" />
      {outcome === 'win' && <rect x="0.75" y="0.75" width="10.5" height="10.5" rx="1.5" className="fill-paper" />}
      {outcome === 'draw' && <path d="M0.75 11.25 L11.25 0.75 V9.75 a1.5 1.5 0 0 1 -1.5 1.5 Z" className="fill-paper" />}
    </svg>
  );
}

const COLUMNS = 'sm:grid-cols-[9rem_minmax(0,1fr)_4.5rem_minmax(0,1.3fr)_7.5rem]';

export default function GameList({ games, onOpen }: GameListProps) {
  return (
    <div>
      <div className={`hidden gap-4 px-3 pb-2 text-sm text-muted sm:grid ${COLUMNS}`} aria-hidden>
        <span>Esito</span>
        <span>Avversario</span>
        <span>Cadenza</span>
        <span>Apertura</span>
        <span className="text-right">Giocata</span>
      </div>

      <ul className="border-t border-rule">
        {games.map((game) => {
          const you = game.yourColor;
          const opponent = you === 'black' ? game.white : game.black;
          const mine = you === 'black' ? game.black : game.white;
          const termination = formatTermination(game.termination);

          return (
            <li key={game.id} className="border-b border-rule">
              <button
                type="button"
                onClick={() => onOpen(game)}
                disabled={!game.isStandard}
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-0.5 px-3 py-2.5 text-left transition-colors hover:bg-deck disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent ${COLUMNS}`}
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <OutcomeMark outcome={game.yourOutcome} />
                  <span className="min-w-0">
                    <span className="block font-medium">{outcomeLabel(game)}</span>
                    <span className="block truncate text-sm text-muted">{termination}</span>
                  </span>
                </span>

                <span className="min-w-0 max-sm:order-3 max-sm:col-span-2 max-sm:pl-[1.375rem]">
                  <span className="block truncate">
                    {opponent.username}
                    {opponent.rating !== null && <span className="ml-1.5 tabular-nums text-muted">{opponent.rating}</span>}
                  </span>
                  <span className="block truncate text-sm text-muted">
                    {you ? `tu col ${you === 'white' ? 'bianco' : 'nero'}` : 'partita di altri'}
                    {mine.rating !== null && you && `, ${mine.rating}`}
                  </span>
                </span>

                <span className="self-center tabular-nums max-sm:order-2 max-sm:text-right">
                  {formatTimeControl(game)}
                  <span className="block text-sm text-muted sm:hidden">{formatPlayedAt(game.playedAt)}</span>
                </span>

                <span className="hidden min-w-0 sm:block" title={game.opening ?? undefined}>
                  <span className="block truncate">{game.isStandard ? (game.opening ?? 'Apertura sconosciuta') : 'Variante non supportata'}</span>
                  <span className="block text-sm text-muted">{game.eco}</span>
                </span>

                <span className="hidden self-center text-right text-sm tabular-nums text-muted sm:block">{formatPlayedAt(game.playedAt)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
