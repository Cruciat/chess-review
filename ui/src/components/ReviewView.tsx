import { useMemo, useState } from 'react';
import type { DrawShape } from 'chessground/draw';
import type { Analysis, Color, GameMeta, MoveClass } from '../api/types';
import { useAnalysis } from '../hooks/useAnalysis';
import { useKeyboard } from '../hooks/useKeyboard';
import { CLASS_STYLE } from '../lib/classes';
import { formatPlayedAt, formatTermination, formatTimeControl, outcomeLabel, parseTimeControl, positionEvalText } from '../lib/format';
import { materialFromFen } from '../lib/material';
import { START, STARTING_FEN, clockAt, fenAt, nextOfClass, sideToMove, uciSquares, whiteWinAt } from '../lib/review';
import AdvantageChart from './AdvantageChart';
import AnalysisProgress from './AnalysisProgress';
import Board from './Board';
import BoardControls from './BoardControls';
import EvalBar from './EvalBar';
import MoveDetail from './MoveDetail';
import MoveList from './MoveList';
import PlayerBar from './PlayerBar';
import Summary from './Summary';

interface ReviewViewProps {
  game: GameMeta;
  username: string | null;
  onBack: () => void;
}

/** Il simbolo della categoria, disegnato nell'angolo della casella d'arrivo. */
function glyphShape(square: DrawShape['orig'], klass: MoveClass): DrawShape {
  const { color, glyph } = CLASS_STYLE[klass];
  const size = glyph.length > 1 ? 19 : 23;
  return {
    orig: square,
    customSvg: {
      html: `<circle cx="80" cy="20" r="17" fill="${color}" stroke="#1b2130" stroke-width="3"/><text x="80" y="21" text-anchor="middle" dominant-baseline="central" font-family="Barlow Condensed, Barlow, sans-serif" font-weight="600" font-size="${size}" fill="#ffffff">${glyph}</text>`,
    },
  };
}

export default function ReviewView({ game, username, onBack }: ReviewViewProps) {
  const { state, retry } = useAnalysis(game.id, username);
  const analysis = state.status === 'done' ? state.analysis : null;

  return (
    <div>
      <GameHeader game={game} onBack={onBack} />

      {analysis ? (
        <Review game={game} analysis={analysis} />
      ) : (
        <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="board-column mx-auto">
            <div className="flex gap-2 opacity-60">
              <div className="w-5 sm:w-6" />
              <div className="flex-1">
                <Board fen={STARTING_FEN} orientation={game.yourColor ?? 'white'} lastMove={null} check={false} shapes={[]} />
              </div>
            </div>
          </div>
          <div className="lg:pt-10">
            {state.status === 'failed' ? (
              <section role="alert">
                <p className="font-medium">L’analisi non è riuscita</p>
                <p className="mt-1 text-sm text-muted">{state.message}</p>
                <button type="button" onClick={retry} className="mt-4 rounded-[3px] bg-paper px-4 py-2 font-medium text-ink hover:bg-white">
                  Riprova l’analisi
                </button>
              </section>
            ) : (
              <AnalysisProgress progress={state.status === 'running' ? state.progress : null} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function GameHeader({ game, onBack }: { game: GameMeta; onBack: () => void }) {
  const termination = formatTermination(game.termination);
  const result = game.yourColor ? [outcomeLabel(game), termination].filter(Boolean).join(' ') : termination;

  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <button type="button" onClick={onBack} className="-ml-2 flex items-center gap-1 rounded-[3px] px-2 py-1 text-sm text-muted hover:bg-deck hover:text-paper">
          <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M15 5l-7 7 7 7" />
          </svg>
          Tutte le partite
        </button>
        <h1 className="mt-1 truncate font-display text-3xl font-semibold leading-tight">
          {game.white.username} <span className="font-normal text-muted">contro</span> {game.black.username}
        </h1>
        <p className="mt-0.5 truncate text-muted">
          {result && <span className="text-paper">{result}</span>}
          {game.opening && <span className={result ? 'ml-3' : ''}>{game.opening}</span>}
        </p>
      </div>
      <div className="flex items-center gap-4 text-sm text-muted">
        <span className="tabular-nums">{formatTimeControl(game)}</span>
        <span>{formatPlayedAt(game.playedAt)}</span>
        <a href={game.url} target="_blank" rel="noreferrer" className="rounded-[3px] px-2 py-1 text-paper underline decoration-muted underline-offset-4 hover:bg-deck">
          Apri su chess.com
        </a>
      </div>
    </div>
  );
}

function Review({ game, analysis }: { game: GameMeta; analysis: Analysis }) {
  const moves = analysis.moves;
  const last = moves.length - 1;
  const [ply, setPly] = useState(START);
  const [flipped, setFlipped] = useState(false);

  const go = (target: number) => setPly(Math.min(last, Math.max(START, target)));

  useKeyboard({
    ArrowLeft: () => go(ply - 1),
    ArrowRight: () => go(ply + 1),
    Home: () => go(START),
    End: () => go(last),
    f: () => setFlipped((v) => !v),
    F: () => setFlipped((v) => !v),
  });

  const baseOrientation: Color = game.yourColor ?? 'white';
  const orientation: Color = flipped ? (baseOrientation === 'white' ? 'black' : 'white') : baseOrientation;
  const bottom = orientation;
  const top: Color = orientation === 'white' ? 'black' : 'white';

  const move = ply > START ? moves[ply] : null;
  const fen = fenAt(analysis, ply);
  const toMove = sideToMove(fen);
  const material = useMemo(() => materialFromFen(fen), [fen]);
  const advantageOf = (color: Color) => Math.max(0, color === 'white' ? material.advantage : -material.advantage);
  // L'orologio si mostra solo nelle partite a tempo con i tempi nel PGN: senza tempi la
  // dotazione iniziale sarebbe falsa, e nelle daily il tempo si misura in giorni.
  const timeControl = parseTimeControl(game.timeControl);
  const hasClocks = timeControl !== null && moves.some((m) => m.clockAfter !== null);
  const initialClock = hasClocks ? timeControl.base : null;

  const lastMove = useMemo(() => (move ? uciSquares(move.uci) : null), [move]);

  const shapes = useMemo<DrawShape[]>(() => {
    if (!move) return [];
    const [, dest] = uciSquares(move.uci);
    const result: DrawShape[] = [glyphShape(dest, move.classification)];
    const judged = move.classification !== 'book' && move.classification !== 'forced';
    if (judged && !move.isBest) {
      const [from, to] = uciSquares(move.bestMoveUci);
      result.unshift({ orig: from, dest: to, brush: 'green' });
    }
    return result;
  }, [move]);

  const evalText = move ? positionEvalText(move) : '0.00';

  const jump = (color: Color, klass: MoveClass) => {
    const target = nextOfClass(moves, ply, color, klass);
    if (target !== null) go(target);
  };

  const sides = { white: game.white, black: game.black };

  return (
    <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="board-column mx-auto min-w-0">
        <PlayerBar side={sides[top]} color={top} clock={hasClocks ? clockAt(moves, ply, top, initialClock) : null} toMove={toMove === top} captured={material.captured[top]} advantage={advantageOf(top)} />
        <div className="flex gap-2">
          <EvalBar whiteWin={whiteWinAt(analysis, ply)} text={evalText} orientation={orientation} />
          <div className="min-w-0 flex-1">
            <Board fen={fen} orientation={orientation} lastMove={lastMove} check={Boolean(move && /[+#]$/.test(move.san))} shapes={shapes} />
          </div>
        </div>
        <PlayerBar side={sides[bottom]} color={bottom} clock={hasClocks ? clockAt(moves, ply, bottom, initialClock) : null} toMove={toMove === bottom} captured={material.captured[bottom]} advantage={advantageOf(bottom)} />

        <div className="mt-2">
          <BoardControls
            atStart={ply === START}
            atEnd={ply === last}
            onFirst={() => go(START)}
            onPrev={() => go(ply - 1)}
            onNext={() => go(ply + 1)}
            onLast={() => go(last)}
            onFlip={() => setFlipped((v) => !v)}
          />
        </div>

        <div className="mt-8">
          <AdvantageChart startWhiteWin={analysis.startWhiteWinPercent} moves={moves} ply={ply} onSelect={go} />
        </div>
      </div>

      {/* Su schermi stretti il dettaglio della mossa sale subito sotto la scacchiera. */}
      <aside className="flex min-w-0 flex-col gap-6 lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:self-start">
        <div className="max-lg:order-3">
          <Summary analysis={analysis} white={game.white} black={game.black} onJump={jump} />
        </div>
        <div className="border-rule max-lg:order-1 lg:border-t lg:pt-4">
          <MoveDetail move={move} />
        </div>
        <div className="flex max-h-80 min-h-[12rem] flex-1 flex-col border-t border-rule pt-3 max-lg:order-2 lg:max-h-none lg:min-h-0">
          <MoveList moves={moves} ply={ply} onSelect={go} />
        </div>
      </aside>
    </div>
  );
}
