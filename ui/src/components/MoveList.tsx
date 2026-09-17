import { useEffect, useMemo, useRef } from 'react';
import type { Move } from '../api/types';
import { CLASS_STYLE } from '../lib/classes';

interface MoveListProps {
  moves: Move[];
  ply: number;
  onSelect: (ply: number) => void;
}

interface Row {
  number: number;
  white?: Move;
  black?: Move;
}

/** Il formulario a due colonne, con le mosse notevoli segnate col loro simbolo. */
export default function MoveList({ moves, ply, onSelect }: MoveListProps) {
  const container = useRef<HTMLDivElement>(null);

  const rows = useMemo(() => {
    const byNumber = new Map<number, Row>();
    for (const move of moves) {
      const row = byNumber.get(move.moveNumber) ?? { number: move.moveNumber };
      row[move.turn] = move;
      byNumber.set(move.moveNumber, row);
    }
    return [...byNumber.values()];
  }, [moves]);

  // Tiene visibile la mossa corrente scorrendo solo l'elenco, non la pagina.
  useEffect(() => {
    const box = container.current;
    const active = box?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!box || !active) return;
    const top = active.offsetTop - box.offsetTop;
    if (top < box.scrollTop + 8) box.scrollTop = top - 8;
    else if (top + active.offsetHeight > box.scrollTop + box.clientHeight - 8) {
      box.scrollTop = top + active.offsetHeight - box.clientHeight + 8;
    }
  }, [ply]);

  const cell = (move: Move | undefined) => {
    if (!move) return <span />;
    const style = CLASS_STYLE[move.classification];
    const current = move.ply === ply;
    return (
      <button
        type="button"
        onClick={() => onSelect(move.ply)}
        aria-current={current}
        className={`flex items-center justify-between rounded-[3px] px-2 py-1 text-left transition-colors ${
          current ? 'bg-paper text-ink' : 'hover:bg-rule'
        }`}
      >
        <span className="font-medium">{move.san}</span>
        {move.isNotable && (
          <span
            className="font-display text-sm font-semibold"
            style={{ color: current ? undefined : style.color }}
            aria-label={style.label}
            title={style.label}
          >
            {style.glyph}
          </span>
        )}
      </button>
    );
  };

  return (
    <div ref={container} className="relative overflow-y-auto overscroll-contain pr-1">
      <ol className="grid grid-cols-[2.25rem_1fr_1fr] gap-x-1 gap-y-0.5 text-[0.95rem]">
        {rows.map((row) => (
          <li key={row.number} className="contents">
            <span className="py-1 pr-1 text-right tabular-nums text-muted">{row.number}.</span>
            {cell(row.white)}
            {cell(row.black)}
          </li>
        ))}
      </ol>
    </div>
  );
}
