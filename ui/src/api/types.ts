// Forma dei dati restituiti dal backend (src/chessreview/api/schemas.py).
// Se cambia lo schema in Python, questo file va aggiornato di pari passo.

export type Color = 'white' | 'black';
export type Outcome = 'win' | 'loss' | 'draw';

export type MoveClass =
  | 'brilliant'
  | 'critical'
  | 'best'
  | 'excellent'
  | 'good'
  | 'inaccuracy'
  | 'mistake'
  | 'blunder'
  | 'missed_win'
  | 'book'
  | 'forced';

export interface Side {
  username: string;
  rating: number | null;
  /** Esito grezzo di chess.com: "win", "resigned", "timeout", ... */
  result: string;
}

export interface GameMeta {
  id: string;
  url: string;
  white: Side;
  black: Side;
  timeClass: string;
  timeControl: string;
  rated: boolean;
  playedAt: string;
  eco: string | null;
  opening: string | null;
  termination: string | null;
  isStandard: boolean;
  yourColor: Color | null;
  yourOutcome: Outcome | null;
}

/** Valutazione dal punto di vista di chi muove, come la manda il backend. */
export interface Evaluation {
  cp: number | null;
  mate: number | null;
  text: string;
}

export interface Alternative {
  san: string;
  uci: string;
  eval: Evaluation;
}

export interface Move {
  ply: number;
  moveNumber: number;
  turn: Color;
  san: string;
  uci: string;
  fenBefore: string;
  fenAfter: string;
  classification: MoveClass;
  label: string;
  isMistake: boolean;
  isNotable: boolean;
  evalBefore: Evaluation;
  evalAfter: Evaluation;
  /** Probabilità di vittoria del bianco dopo la mossa, 0–100. */
  whiteWinPercent: number;
  winPercentDrop: number;
  accuracy: number;
  bestMoveSan: string;
  bestMoveUci: string;
  isBest: boolean;
  isOpening: boolean;
  timeSpent: number | null;
  clockAfter: number | null;
  materialSacrificed: number;
  depth: number;
  alternatives: Alternative[];
}

export interface PlayerReport {
  color: Color;
  moves: number;
  accuracy: number;
  acpl: number;
  bestMoveRate: number;
  counts: Partial<Record<MoveClass, number>>;
}

export interface Analysis {
  moves: Move[];
  white: PlayerReport;
  black: PlayerReport;
  deepPositions: number;
  startWhiteWinPercent: number;
  game?: GameMeta;
}

export type Phase = 'scan' | 'deep';

export interface Progress {
  phase: Phase;
  done: number;
  total: number;
}

export interface RatingStats {
  timeClass: 'rapid' | 'blitz' | 'bullet' | 'daily';
  rating: number | null;
  best: number | null;
  wins: number;
  losses: number;
  draws: number;
}

export interface PlayerProfile {
  username: string;
  name: string | null;
  title: string | null;
  avatar: string | null;
  /** Codice ISO a due lettere, es. "IT". */
  country: string | null;
  joined: string | null;
  lastOnline: string | null;
  league: string | null;
  url: string | null;
  ratings: RatingStats[];
}
