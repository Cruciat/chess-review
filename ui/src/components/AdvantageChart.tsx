import { useMemo, useRef, useState } from 'react';
import type { Move } from '../api/types';
import { useElementWidth } from '../hooks/useElementWidth';
import { CLASS_STYLE } from '../lib/classes';
import { moveLabel, positionEvalText } from '../lib/format';

interface AdvantageChartProps {
  startWhiteWin: number;
  moves: Move[];
  ply: number;
  onSelect: (ply: number) => void;
}

const HEIGHT = 120;
const PAD_X = 8;
const PAD_Y = 8;

/**
 * L'andamento della partita in probabilità di vittoria del bianco.
 *
 * Disegnato a mano in SVG invece che con Recharts: servono i punti
 * colorati sulle mosse notevoli, il cursore sulla posizione mostrata e
 * la selezione trascinando, tutte cose scomode in Recharts 3, che
 * pesava da solo più di metà del bundle.
 */
export default function AdvantageChart({ startWhiteWin, moves, ply, onSelect }: AdvantageChartProps) {
  const [container, width] = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const dragging = useRef(false);

  const values = useMemo(() => [startWhiteWin, ...moves.map((m) => m.whiteWinPercent)], [startWhiteWin, moves]);
  const n = values.length;
  const innerWidth = Math.max(0, width - PAD_X * 2);
  const x = (i: number) => PAD_X + (n > 1 ? (i * innerWidth) / (n - 1) : 0);
  const y = (v: number) => PAD_Y + (HEIGHT - PAD_Y * 2) * (1 - v / 100);

  const line = values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  const area = `${line}L${x(n - 1).toFixed(1)},${HEIGHT}L${x(0).toFixed(1)},${HEIGHT}Z`;

  /** Indice del punto più vicino al puntatore; l'indice 0 è la posizione iniziale. */
  const indexAt = (clientX: number, rect: DOMRect) => {
    if (n <= 1 || innerWidth === 0) return 0;
    const ratio = (clientX - rect.left - PAD_X) / innerWidth;
    return Math.min(n - 1, Math.max(0, Math.round(ratio * (n - 1))));
  };

  const cursor = ply + 1;
  const hovered = hover === null ? null : hover === 0 ? null : moves[hover - 1];
  const tooltipLeft = hover === null ? 0 : Math.min(Math.max(x(hover), 60), Math.max(60, width - 60));

  return (
    <div
      ref={container}
      className="relative touch-none select-none"
      style={{ height: HEIGHT }}
      onPointerDown={(event) => {
        dragging.current = true;
        event.currentTarget.setPointerCapture(event.pointerId);
        onSelect(indexAt(event.clientX, event.currentTarget.getBoundingClientRect()) - 1);
      }}
      onPointerMove={(event) => {
        const index = indexAt(event.clientX, event.currentTarget.getBoundingClientRect());
        setHover(index);
        if (dragging.current) onSelect(index - 1);
      }}
      onPointerUp={() => {
        dragging.current = false;
      }}
      onPointerLeave={() => setHover(null)}
      role="group"
      aria-label="Andamento della partita: clicca o trascina per scegliere la posizione"
    >
      {width > 0 && (
        <svg width={width} height={HEIGHT} className="block overflow-visible rounded-[3px] bg-well">
          <path d={area} className="fill-paper" />
          <line x1={0} x2={width} y1={y(50)} y2={y(50)} className="stroke-muted/40" strokeDasharray="2 4" />

          {hover !== null && hover !== cursor && (
            <line x1={x(hover)} x2={x(hover)} y1={0} y2={HEIGHT} className="stroke-muted/50" />
          )}

          {moves.map((move, i) =>
            move.isNotable ? (
              <circle
                key={move.ply}
                cx={x(i + 1)}
                cy={y(move.whiteWinPercent)}
                r={4}
                fill={CLASS_STYLE[move.classification].color}
                className="stroke-well"
                strokeWidth={1.5}
              />
            ) : null,
          )}

          {/* Il cursore in differenza di colore resta visibile sia sul bianco sia sul nero. */}
          <line x1={x(cursor)} x2={x(cursor)} y1={0} y2={HEIGHT} stroke="white" strokeWidth={2} style={{ mixBlendMode: 'difference' }} />
        </svg>
      )}

      {hover !== null && (
        <div
          className="pointer-events-none absolute -top-8 -translate-x-1/2 whitespace-nowrap rounded-[3px] bg-deck px-2 py-1 text-xs tabular-nums shadow-lg ring-1 ring-rule"
          style={{ left: tooltipLeft }}
        >
          {hovered ? (
            <>
              <span className="font-medium">{moveLabel(hovered)}</span>
              <span className="ml-2 text-muted">{positionEvalText(hovered)}</span>
            </>
          ) : (
            <span className="font-medium">Posizione iniziale</span>
          )}
        </div>
      )}
    </div>
  );
}
