import { useEffect, useRef } from 'react';
import type { Color, Side } from '../api/types';
import { formatClock } from '../lib/format';
import type { Role } from '../lib/material';

interface PlayerBarProps {
  side: Side;
  color: Color;
  /** Secondi sull'orologio nella posizione mostrata, se la partita ha orologio. */
  clock: number | null;
  /** Tocca a questo giocatore: il suo orologio è quello che scorre. */
  toMove: boolean;
  /** Pezzi avversari catturati da questo giocatore. */
  captured: Role[];
  /** Punti di materiale di vantaggio, se è avanti. */
  advantage: number;
}

const ROLE_NAMES: Record<Role, string> = { pawn: 'pedone', knight: 'cavallo', bishop: 'alfiere', rook: 'torre', queen: 'donna' };

/**
 * Un pezzo disegnato con le stesse immagini della scacchiera. Lo stile di
 * chessground seleziona l'elemento <piece>, che React segnalerebbe come tag
 * sconosciuto: si crea a mano dentro un contenitore.
 */
function PieceIcon({ role, color }: { role: Role; color: Color }) {
  const holder = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const piece = document.createElement('piece');
    piece.className = `${role} ${color}`;
    holder.current?.replaceChildren(piece);
  }, [role, color]);

  return <span ref={holder} className="captured-piece" />;
}

/** I pezzi catturati, raggruppati per tipo e sovrapposti come sui siti di scacchi. */
function CapturedPieces({ roles, color }: { roles: Role[]; color: Color }) {
  const groups = roles.reduce<Role[][]>((acc, role) => {
    const last = acc[acc.length - 1];
    if (last && last[0] === role) last.push(role);
    else acc.push([role]);
    return acc;
  }, []);

  return (
    <span className="captured cg-wrap" aria-label={`Ha catturato: ${roles.map((r) => ROLE_NAMES[r]).join(', ')}`}>
      {groups.map((group) => (
        <span key={group[0]} className="captured-group">
          {group.map((role, i) => (
            <PieceIcon key={i} role={role} color={color} />
          ))}
        </span>
      ))}
    </span>
  );
}

export default function PlayerBar({ side, color, clock, toMove, captured, advantage }: PlayerBarProps) {
  const opponent: Color = color === 'white' ? 'black' : 'white';

  return (
    <div className="flex h-10 items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden
          className={`size-3 shrink-0 rounded-[2px] border ${color === 'white' ? 'border-paper bg-paper' : 'border-muted/60 bg-[#0f131c]'}`}
        />
        <span className="truncate font-medium">{side.username}</span>
        {side.rating !== null && <span className="text-sm tabular-nums text-muted">{side.rating}</span>}
        {captured.length > 0 && <CapturedPieces roles={captured} color={opponent} />}
        {advantage > 0 && <span className="text-sm tabular-nums text-muted">+{advantage}</span>}
      </div>
      {clock !== null && (
        <span
          className={`shrink-0 rounded-[3px] px-2 py-0.5 font-display text-lg font-semibold tabular-nums leading-tight ${
            toMove ? 'bg-paper text-ink' : 'bg-deck text-muted'
          }`}
          aria-label={`Orologio ${formatClock(clock)}`}
        >
          {formatClock(clock)}
        </span>
      )}
    </div>
  );
}
