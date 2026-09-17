import { useEffect, useRef } from 'react';
import { Chessground } from 'chessground';
import type { Api } from 'chessground/api';
import type { DrawBrushes, DrawShape } from 'chessground/draw';
import type { Key } from 'chessground/types';
import type { Color } from '../api/types';
import { sideToMove } from '../lib/review';

/** I pennelli base di chessground, ricolorati con la palette delle categorie. */
const BRUSHES: DrawBrushes = {
  green: { key: 'g', color: '#6db26a', opacity: 0.9, lineWidth: 10 },
  red: { key: 'r', color: '#d64b45', opacity: 0.9, lineWidth: 10 },
  blue: { key: 'b', color: '#5b8fe0', opacity: 0.9, lineWidth: 10 },
  yellow: { key: 'y', color: '#e2be4a', opacity: 0.9, lineWidth: 10 },
};

interface BoardProps {
  fen: string;
  orientation: Color;
  lastMove: [Key, Key] | null;
  check: boolean;
  shapes: DrawShape[];
}

/**
 * Scacchiera di sola visualizzazione.
 *
 * L'istanza di chessground si crea una volta al montaggio e si distrugge
 * solo allo smontaggio; ogni cambiamento successivo passa da set(). La
 * versione precedente la distruggeva a ogni cambio di posizione, e sotto
 * StrictMode ne creava due sullo stesso elemento.
 */
export default function Board({ fen, orientation, lastMove, check, shapes }: BoardProps) {
  const element = useRef<HTMLDivElement>(null);
  const api = useRef<Api | null>(null);

  useEffect(() => {
    if (!element.current) return;
    const cg = Chessground(element.current, {
      viewOnly: true,
      coordinates: true,
      animation: { enabled: true, duration: 160 },
      drawable: { enabled: false, visible: true, brushes: BRUSHES },
    });
    api.current = cg;
    return () => {
      cg.destroy();
      api.current = null;
    };
  }, []);

  useEffect(() => {
    const cg = api.current;
    if (!cg) return;
    cg.set({
      fen,
      orientation,
      turnColor: sideToMove(fen),
      lastMove: lastMove ?? undefined,
      check,
    });
    cg.setAutoShapes(shapes);
  }, [fen, orientation, lastMove, check, shapes]);

  return <div ref={element} className="aspect-square w-full" />;
}
