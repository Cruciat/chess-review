import type { Move } from '../api/types';
import { CLASS_STYLE } from '../lib/classes';
import { formatPercent, moveLabel, positionEvalText, whiteEvalText } from '../lib/format';

interface MoveDetailProps {
  move: Move | null;
}

/** Cosa è successo nella mossa mostrata, e cosa si poteva giocare. */
export default function MoveDetail({ move }: MoveDetailProps) {
  if (!move) {
    return (
      <section aria-live="polite" className="min-h-[9.5rem]">
        <p className="font-medium">Posizione iniziale</p>
        <p className="mt-1 text-sm text-muted">Scorri la partita con le frecce, oppure clicca una mossa o un punto del grafico.</p>
      </section>
    );
  }

  const style = CLASS_STYLE[move.classification];
  const judged = move.classification !== 'book' && move.classification !== 'forced';

  return (
    <section aria-live="polite" className="min-h-[9.5rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-lg font-semibold">{moveLabel(move)}</p>
        <p className="font-display text-lg font-semibold tabular-nums">{positionEvalText(move)}</p>
      </div>

      <p className="mt-0.5 flex items-center gap-2 font-medium" style={{ color: style.color }}>
        <span className="font-display text-lg font-semibold">{style.glyph}</span>
        {style.label}
        {judged && move.winPercentDrop >= 1 && (
          <span className="text-sm font-normal text-muted">
            perde {formatPercent(move.winPercentDrop)} punti di probabilità
          </span>
        )}
      </p>

      {move.classification === 'book' && <p className="mt-2 text-sm text-muted">Mossa d'apertura: non viene giudicata.</p>}
      {move.classification === 'forced' && <p className="mt-2 text-sm text-muted">Era l'unica mossa legale.</p>}

      {judged && (
        <ul className="mt-3 space-y-0.5 text-sm">
          {move.alternatives.map((alt) => {
            const played = alt.uci === move.uci;
            const best = alt.uci === move.bestMoveUci;
            // Le varianti sono in ordine dalla migliore: basta dire quale è stata giocata,
            // e segnare la migliore solo quando non è quella.
            const note = played ? 'giocata' : best ? 'migliore' : null;
            return (
              <li key={alt.uci} className={`flex justify-between gap-3 rounded-[3px] px-2 py-0.5 ${played ? 'bg-rule/70' : ''}`}>
                <span>
                  <span className="font-medium">{alt.san}</span>
                  {note && <span className="ml-2 text-muted">{note}</span>}
                </span>
                <span className="tabular-nums text-muted">{whiteEvalText(alt.eval, move.turn)}</span>
              </li>
            );
          })}
          {!move.alternatives.some((alt) => alt.uci === move.uci) && (
            <li className="flex justify-between gap-3 rounded-[3px] bg-rule/70 px-2 py-0.5">
              <span>
                <span className="font-medium">{move.san}</span>
                <span className="ml-2 text-muted">giocata</span>
              </span>
              <span className="tabular-nums text-muted">{whiteEvalText(move.evalAfter, move.turn)}</span>
            </li>
          )}
        </ul>
      )}

      {move.timeSpent !== null && (
        <p className="mt-2 text-sm text-muted">
          Pensata {move.timeSpent < 10 ? formatPercent(move.timeSpent) : Math.round(move.timeSpent)} s
        </p>
      )}
    </section>
  );
}
