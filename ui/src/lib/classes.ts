// Aspetto delle categorie di mossa: colore, simbolo e ordine.
// I simboli sono la notazione scacchistica standard (!!, !, ?!, ?, ??)
// e non i glifi di chess.com, che chiede di non riusarli.

import type { MoveClass } from '../api/types';

export interface ClassStyle {
  label: string;
  glyph: string;
  color: string;
}

export const CLASS_STYLE: Record<MoveClass, ClassStyle> = {
  brilliant: { label: 'Brillante', glyph: '!!', color: '#3fb8c8' },
  critical: { label: 'Unica', glyph: '!', color: '#5b8fe0' },
  best: { label: 'Migliore', glyph: '★', color: '#6db26a' },
  excellent: { label: 'Ottima', glyph: '✓', color: '#97c27e' },
  good: { label: 'Buona', glyph: '✓', color: '#a9b09a' },
  inaccuracy: { label: 'Imprecisione', glyph: '?!', color: '#e2be4a' },
  mistake: { label: 'Errore', glyph: '?', color: '#e58a3b' },
  blunder: { label: 'Blunder', glyph: '??', color: '#d64b45' },
  missed_win: { label: 'Vittoria mancata', glyph: '✕', color: '#b369d0' },
  book: { label: 'Apertura', glyph: '≡', color: '#a89272' },
  forced: { label: 'Forzata', glyph: '→', color: '#7e8898' },
};

/** Righe del riepilogo, dalla migliore alla peggiore. Le mosse d'apertura non sono giudicate. */
export const SUMMARY_ORDER: MoveClass[] = [
  'brilliant',
  'critical',
  'best',
  'excellent',
  'good',
  'inaccuracy',
  'mistake',
  'blunder',
  'missed_win',
  'forced',
];
