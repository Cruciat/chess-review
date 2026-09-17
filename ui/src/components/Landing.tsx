import type { DrawShape } from 'chessground/draw';
import type { Key } from 'chessground/types';
import { CLASS_STYLE } from '../lib/classes';
import Board from './Board';

interface LandingProps {
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
}

/** Partita dell'Opera, Parigi 1858: la posizione subito dopo 16.Qb8+. */
const OPERA_FEN = '1Q2kb1r/p2n1ppp/4q3/4p1B1/4P3/8/PPP2PPP/2KR4 b k - 1 16';
const OPERA_LAST_MOVE: [Key, Key] = ['b3', 'b8'];
const OPERA_SHAPES: DrawShape[] = [
  {
    orig: 'b8',
    customSvg: {
      html: `<circle cx="80" cy="20" r="17" fill="${CLASS_STYLE.brilliant.color}" stroke="#1b2130" stroke-width="3"/><text x="80" y="21" text-anchor="middle" dominant-baseline="central" font-family="Barlow Condensed, Barlow, sans-serif" font-weight="600" font-size="19" fill="#ffffff">!!</text>`,
    },
  },
];

const STEPS = [
  {
    title: 'Scrivi il tuo username',
    text: 'Arrivano le ultime partite pubbliche da chess.com, con avversario, cadenza e apertura. Non serve fare login.',
  },
  {
    title: 'Scegli una partita',
    text: 'Stockfish la analizza sul tuo computer: prima una scansione di tutte le posizioni, poi un riesame delle mosse sospette.',
  },
  {
    title: 'Rivedila mossa per mossa',
    text: 'Accuratezza dei due giocatori, ogni mossa classificata dalla brillante al blunder, e le alternative che il motore avrebbe giocato.',
  },
];

export default function Landing({ draft, onDraftChange, onSubmit }: LandingProps) {
  return (
    <div className="grid items-center gap-x-16 gap-y-12 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,27rem)] lg:py-16">
      <div>
        <h1 className="max-w-[20ch] font-display text-5xl font-semibold leading-[0.95] text-balance sm:text-6xl">
          Rivedi ogni partita, non solo una al giorno
        </h1>
        <p className="mt-5 max-w-[56ch] text-lg text-muted">
          chessreview è la review di chess.com fatta in casa: scarica le tue partite e le fa analizzare a Stockfish, senza account premium e senza
          limiti.
        </p>

        <form
          className="mt-8 flex max-w-xl flex-col gap-3 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <label htmlFor="landing-username" className="sr-only">
            Username di chess.com
          </label>
          <input
            id="landing-username"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="Il tuo username di chess.com"
            autoComplete="username"
            spellCheck={false}
            autoFocus
            className="h-14 w-full min-w-0 rounded-[3px] sm:flex-1 border border-rule bg-well px-4 text-lg placeholder:text-muted/70 focus:border-muted focus:outline-none"
          />
          <button
            type="submit"
            disabled={!draft.trim()}
            className="h-14 shrink-0 rounded-[3px] bg-paper px-6 text-lg font-medium text-ink hover:bg-white disabled:opacity-50"
          >
            Carica partite
          </button>
        </form>

        <ol className="mt-12 grid max-w-3xl gap-6 border-t border-rule pt-6 sm:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.title}>
              <p className="font-medium">
                <span className="mr-2 font-display text-muted">{i + 1}</span>
                {step.title}
              </p>
              <p className="mt-1 text-sm text-muted">{step.text}</p>
            </li>
          ))}
        </ol>
      </div>

      <figure className="mx-auto w-full max-w-[27rem] max-lg:max-w-sm">
        <Board fen={OPERA_FEN} orientation="white" lastMove={OPERA_LAST_MOVE} check shapes={OPERA_SHAPES} />
        <figcaption className="mt-3 text-sm text-muted">
          <span className="text-paper">16.Qb8+, brillante.</span> Morphy sacrifica la donna e alla mossa dopo dà matto con la torre. Partita
          dell'Opera, Parigi 1858.
        </figcaption>
      </figure>
    </div>
  );
}
