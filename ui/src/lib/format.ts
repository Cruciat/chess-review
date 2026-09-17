// Formattazione di valutazioni, orologi, date e metadati di partita.

import type { Color, Evaluation, GameMeta, Move } from '../api/types';

const decimal = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function formatPercent(value: number): string {
  return decimal.format(value);
}

/** "7." per il bianco, "7…" per il nero. */
export function moveNumberLabel(move: Pick<Move, 'moveNumber' | 'turn'>): string {
  return move.turn === 'white' ? `${move.moveNumber}.` : `${move.moveNumber}…`;
}

export function moveLabel(move: Pick<Move, 'moveNumber' | 'turn' | 'san'>): string {
  return `${moveNumberLabel(move)} ${move.san}`;
}

/**
 * Valutazione dal punto di vista del bianco, in notazione scacchistica
 * (col punto decimale, come su qualunque sito di scacchi).
 * Il backend la manda orientata su chi ha mosso: qui si riorienta.
 */
export function whiteEvalText(evaluation: Evaluation, mover: Color): string {
  const sign = mover === 'white' ? 1 : -1;
  if (evaluation.mate !== null) {
    const mate = evaluation.mate * sign;
    return mate > 0 ? `#${mate}` : `#-${Math.abs(mate)}`;
  }
  const cp = (evaluation.cp ?? 0) * sign;
  const pawns = (cp / 100).toFixed(2);
  return cp > 0 ? `+${pawns}` : pawns;
}

/** La valutazione della posizione dopo una mossa; a matto dato, il risultato. */
export function positionEvalText(move: Move): string {
  if (move.san.endsWith('#')) return move.turn === 'white' ? '1-0' : '0-1';
  return whiteEvalText(move.evalAfter, move.turn);
}

/** "3:05", "1:02:05" oltre l'ora, oppure "0:08.4" sotto i dieci secondi, quando i decimi contano. */
export function formatClock(seconds: number): string {
  const safe = Math.max(0, seconds);
  if (safe >= 3600) {
    const hours = Math.floor(safe / 3600);
    const minutes = Math.floor((safe % 3600) / 60);
    const secs = Math.floor(safe % 60);
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  const minutes = Math.floor(safe / 60);
  const rest = safe - minutes * 60;
  if (safe < 10) return `${minutes}:${rest.toFixed(1).padStart(4, '0')}`;
  return `${minutes}:${String(Math.floor(rest)).padStart(2, '0')}`;
}

/** "180+2" diventa { base: 180, increment: 2 }; le daily ("1/86400") non hanno orologio. */
export function parseTimeControl(raw: string): { base: number; increment: number } | null {
  const match = /^(\d+)(?:\+(\d+))?$/.exec(raw.trim());
  if (!match) return null;
  return { base: Number(match[1]), increment: Number(match[2] ?? 0) };
}

/** "180+2" diventa "3+2", "600" diventa "10 min", le daily "1 giorno". */
export function formatTimeControl(game: Pick<GameMeta, 'timeControl' | 'timeClass'>): string {
  const parsed = parseTimeControl(game.timeControl);
  if (!parsed) {
    const daily = /^1\/(\d+)$/.exec(game.timeControl);
    if (daily) {
      const days = Math.round(Number(daily[1]) / 86400);
      return days === 1 ? '1 giorno' : `${days} giorni`;
    }
    return game.timeClass;
  }
  const minutes = parsed.base / 60;
  const base = Number.isInteger(minutes) ? String(minutes) : minutes.toFixed(1);
  return parsed.increment ? `${base}+${parsed.increment}` : `${base} min`;
}

const dayFormat = new Intl.DateTimeFormat('it-IT', { day: 'numeric', month: 'short' });
const yearFormat = new Intl.DateTimeFormat('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
const timeFormat = new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' });

export function formatPlayedAt(iso: string, now = new Date()): string {
  const date = new Date(iso);
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);
  const time = timeFormat.format(date);

  if (days === 0) return `oggi, ${time}`;
  if (days === 1) return `ieri, ${time}`;
  if (date.getFullYear() === now.getFullYear()) return `${dayFormat.format(date)}, ${time}`;
  return yearFormat.format(date);
}

const TERMINATIONS: [RegExp, string][] = [
  [/checkmate/i, 'per scacco matto'],
  [/resignation/i, 'per abbandono'],
  [/timeout vs insufficient material/i, 'tempo contro materiale insufficiente'],
  [/on time/i, 'a tempo'],
  [/abandoned/i, 'per partita abbandonata'],
  [/agreement/i, "d'accordo"],
  [/repetition/i, 'per ripetizione'],
  [/stalemate/i, 'per stallo'],
  [/insufficient material/i, 'per materiale insufficiente'],
  [/50[- ]move/i, 'per la regola delle 50 mosse'],
];

/** "Cruciat won by resignation" diventa "per abbandono". */
export function formatTermination(termination: string | null): string | null {
  if (!termination) return null;
  for (const [pattern, text] of TERMINATIONS) {
    if (pattern.test(termination)) return text;
  }
  return null;
}

export function outcomeLabel(game: GameMeta): string {
  switch (game.yourOutcome) {
    case 'win':
      return 'Vinta';
    case 'loss':
      return 'Persa';
    case 'draw':
      return 'Patta';
    default:
      return '';
  }
}
