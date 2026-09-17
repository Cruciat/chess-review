// Stato della review derivato da un solo numero: la semimossa corrente.
// START (-1) è la posizione iniziale, 0 la posizione dopo la prima mossa,
// e così via. Tenerla distinta dalla prima mossa è ciò che permette di
// vedere 1.e4 sulla scacchiera e nell'elenco.

import type { Key } from 'chessground/types';
import type { Analysis, Color, Move, MoveClass } from '../api/types';

export const START = -1;

export const STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

export function fenAt(analysis: Analysis, ply: number): string {
  if (ply <= START) return analysis.moves[0]?.fenBefore ?? STARTING_FEN;
  return analysis.moves[ply].fenAfter;
}

export function whiteWinAt(analysis: Analysis, ply: number): number {
  return ply <= START ? analysis.startWhiteWinPercent : analysis.moves[ply].whiteWinPercent;
}

export function sideToMove(fen: string): Color {
  return fen.split(' ')[1] === 'b' ? 'black' : 'white';
}

/** "e2e4" diventa ["e2", "e4"]; la promozione ("e7e8q") perde il pezzo. */
export function uciSquares(uci: string): [Key, Key] {
  return [uci.slice(0, 2) as Key, uci.slice(2, 4) as Key];
}

/**
 * Secondi sull'orologio di un giocatore nella posizione corrente:
 * quelli dopo la sua ultima mossa, oppure la dotazione iniziale se
 * non ha ancora mosso. Null se la partita non ha orologio.
 */
export function clockAt(moves: Move[], ply: number, color: Color, initial: number | null): number | null {
  for (let i = Math.min(ply, moves.length - 1); i >= 0; i--) {
    if (moves[i].turn === color && moves[i].clockAfter !== null) return moves[i].clockAfter;
  }
  return initial;
}

/** La prossima mossa di un colore con una data categoria, ricominciando dall'inizio in fondo. */
export function nextOfClass(moves: Move[], from: number, color: Color, klass: MoveClass): number | null {
  const n = moves.length;
  for (let step = 1; step <= n; step++) {
    const i = (((from + step) % n) + n) % n;
    if (moves[i].turn === color && moves[i].classification === klass) return i;
  }
  return null;
}
