import type { Color } from '../api/types';

interface EvalBarProps {
  /** Probabilità di vittoria del bianco, 0–100. */
  whiteWin: number;
  /** Valutazione già dal punto di vista del bianco: "+1.66", "#-3", "1-0". */
  text: string;
  orientation: Color;
}

/**
 * Barra verticale del vantaggio. La parte chiara è il bianco e sta dal
 * lato del bianco sulla scacchiera, quindi si capovolge con essa.
 * È in probabilità di vittoria e non in pedoni, come il grafico: a +8
 * la barra è piena, e un pedone in più non la sposta.
 */
export default function EvalBar({ whiteWin, text, orientation }: EvalBarProps) {
  const share = Math.min(100, Math.max(0, whiteWin));
  const whiteAtBottom = orientation === 'white';
  const whiteAhead = share >= 50;
  // Il numero sta in fondo alla parte di chi è avanti, sul suo colore.
  const labelAtBottom = whiteAhead === whiteAtBottom;

  return (
    <div
      className="relative w-5 shrink-0 overflow-hidden rounded-[3px] bg-[#0f131c] sm:w-6"
      role="img"
      aria-label={`Valutazione ${text}`}
    >
      <div
        className={`absolute inset-x-0 bg-paper transition-[height] duration-300 ease-out motion-reduce:transition-none ${
          whiteAtBottom ? 'bottom-0' : 'top-0'
        }`}
        style={{ height: `${share}%` }}
      />
      <span
        className={`absolute inset-x-0 text-center font-display text-[10px] font-semibold tabular-nums leading-none sm:text-[11px] ${
          labelAtBottom ? 'bottom-1.5' : 'top-1.5'
        } ${whiteAhead ? 'text-ink' : 'text-paper'}`}
      >
        {text.replace(/^\+/, '')}
      </span>
    </div>
  );
}
