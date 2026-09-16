import { useEffect, useRef, useState } from 'react';
import { Chessground } from 'chessground';
import type { Api } from 'chessground/api';

interface BoardProps {
  fen: string;
  orientation?: 'white' | 'black';
}

export default function Board({ fen, orientation = 'white' }: BoardProps) {
  const boardRef = useRef<HTMLDivElement>(null);
  const [api, setApi] = useState<Api | null>(null);

  useEffect(() => {
    if (boardRef.current && !api) {
      const cg = Chessground(boardRef.current, {
        fen,
        orientation,
        viewOnly: true,
      });
      setApi(cg);
    }
    return () => {
      api?.destroy();
    };
  }, [api, fen, orientation]);

  useEffect(() => {
    if (api) {
      api.set({ fen });
    }
  }, [api, fen]);

  return <div ref={boardRef} className="w-full aspect-square max-w-[600px]" />;
}
