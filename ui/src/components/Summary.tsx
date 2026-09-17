import type { Analysis, Color, MoveClass, Side } from '../api/types';
import { CLASS_STYLE, SUMMARY_ORDER } from '../lib/classes';
import { formatPercent } from '../lib/format';

interface SummaryProps {
  analysis: Analysis;
  white: Side;
  black: Side;
  /** Porta alla prossima mossa di quel colore con quella categoria. */
  onJump: (color: Color, klass: MoveClass) => void;
}

function Chip({ color }: { color: Color }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-2.5 shrink-0 rounded-[2px] border ${
        color === 'white' ? 'border-paper bg-paper' : 'border-muted/60 bg-[#0f131c]'
      }`}
    />
  );
}

export default function Summary({ analysis, white, black, onJump }: SummaryProps) {
  const columns = [
    { color: 'white' as const, side: white, report: analysis.white },
    { color: 'black' as const, side: black, report: analysis.black },
  ];

  return (
    <section aria-label="Riepilogo della partita">
      <div className="grid grid-cols-[1fr_5.5rem_5.5rem] items-end gap-x-2">
        <span />
        {columns.map(({ color, side }) => (
          <span key={color} className="flex min-w-0 items-center justify-end gap-1.5 text-sm text-muted">
            <Chip color={color} />
            <span className="truncate">{side.username}</span>
          </span>
        ))}

        <span className="pb-1.5 text-sm text-muted">Accuratezza</span>
        {columns.map(({ color, report }) => (
          <span key={color} className="text-right font-display text-[2.6rem] font-semibold leading-none tabular-nums">
            {formatPercent(report.accuracy)}
          </span>
        ))}
      </div>

      <table className="mt-3 w-full border-collapse text-sm">
        <caption className="sr-only">Mosse per categoria</caption>
        <tbody>
          {SUMMARY_ORDER.map((klass) => {
            const style = CLASS_STYLE[klass];
            const counts = columns.map(({ color, report }) => ({ color, count: report.counts[klass] ?? 0 }));
            // Le categorie assenti in entrambi i colori non dicono nulla e tolgono spazio al formulario.
            if (counts.every((c) => c.count === 0)) return null;
            return (
              <tr key={klass} className="border-t border-rule/60">
                <th scope="row" className="py-0.5 text-left font-normal">
                  <span className="inline-flex items-center gap-2">
                    <span className="w-5 text-center font-display font-semibold" style={{ color: style.color }}>
                      {style.glyph}
                    </span>
                    {style.label}
                  </span>
                </th>
                {counts.map(({ color, count }) => (
                  <td key={color} className="w-[5.5rem] py-0.5 pl-2 text-right">
                    {count > 0 ? (
                      <button
                        type="button"
                        onClick={() => onJump(color, klass)}
                        className="rounded-[3px] px-2 py-0.5 font-medium tabular-nums hover:bg-rule"
                        title={`Vai alla prossima mossa del ${color === 'white' ? 'bianco' : 'nero'} di questo tipo`}
                      >
                        {count}
                      </button>
                    ) : (
                      <span className="px-2 tabular-nums">0</span>
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
