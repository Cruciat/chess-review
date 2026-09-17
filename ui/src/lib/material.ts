// Materiale sulla scacchiera, ricavato dal FEN: i pezzi che ciascun lato
// ha catturato e il vantaggio in punti. Serve a capire a colpo d'occhio
// se conviene cambiare: chi è avanti di materiale semplifica volentieri.

import type { Color } from '../api/types';

export type Role = 'pawn' | 'knight' | 'bishop' | 'rook' | 'queen';

/** Dal meno al più prezioso: l'ordine in cui si mostrano i pezzi catturati. */
export const ROLES: Role[] = ['pawn', 'knight', 'bishop', 'rook', 'queen'];

const START: Record<Role, number> = { pawn: 8, knight: 2, bishop: 2, rook: 2, queen: 1 };
const VALUE: Record<Role, number> = { pawn: 1, knight: 3, bishop: 3, rook: 5, queen: 9 };
const LETTER: Record<string, Role> = { p: 'pawn', n: 'knight', b: 'bishop', r: 'rook', q: 'queen' };

export interface Material {
  /** Pezzi dell'avversario catturati da ciascun colore. */
  captured: Record<Color, Role[]>;
  /** Punti di materiale del bianco meno quelli del nero. */
  advantage: number;
}

type Counts = Record<Role, number>;

const emptyCounts = (): Counts => ({ pawn: 0, knight: 0, bishop: 0, rook: 0, queen: 0 });

/**
 * Pezzi mancanti di un colore rispetto alla posizione iniziale.
 * Un pezzo in più del normale è un pedone promosso: quel pedone non è
 * stato catturato, quindi non va contato fra quelli mancanti.
 */
function missing(counts: Counts): Role[] {
  const promoted = ROLES.filter((r) => r !== 'pawn').reduce((sum, r) => sum + Math.max(0, counts[r] - START[r]), 0);
  const result: Role[] = [];
  for (const role of ROLES) {
    const expected = role === 'pawn' ? START.pawn - promoted : START[role];
    for (let i = counts[role]; i < expected; i++) result.push(role);
  }
  return result;
}

export function materialFromFen(fen: string): Material {
  const counts: Record<Color, Counts> = { white: emptyCounts(), black: emptyCounts() };
  for (const char of fen.split(' ')[0]) {
    const role = LETTER[char.toLowerCase()];
    if (role) counts[char === char.toLowerCase() ? 'black' : 'white'][role]++;
  }

  const points = (c: Counts) => ROLES.reduce((sum, r) => sum + c[r] * VALUE[r], 0);

  return {
    captured: { white: missing(counts.black), black: missing(counts.white) },
    advantage: points(counts.white) - points(counts.black),
  };
}
