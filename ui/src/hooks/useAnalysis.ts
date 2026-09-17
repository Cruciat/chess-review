import { useCallback, useEffect, useState } from 'react';
import { streamAnalysis } from '../api/client';
import type { Analysis, Progress } from '../api/types';

export type AnalysisState =
  | { status: 'running'; progress: Progress | null }
  | { status: 'done'; analysis: Analysis }
  | { status: 'failed'; message: string };

/**
 * Analisi di una partita, dal primo avanzamento al risultato.
 *
 * Il componente che lo usa va montato con key={id della partita}: così
 * cambiare partita riparte da uno stato pulito invece di mostrare per un
 * attimo l'analisi precedente. Se la stessa partita è già in analisi,
 * il backend aggancia questa richiesta a quella in corso.
 */
export function useAnalysis(gameId: string, username: string | null) {
  const [state, setState] = useState<AnalysisState>({ status: 'running', progress: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    return streamAnalysis(gameId, username, {
      onProgress: (progress) => setState({ status: 'running', progress }),
      onResult: (analysis) => setState({ status: 'done', analysis }),
      onFailure: (message) => setState({ status: 'failed', message }),
    });
  }, [gameId, username, attempt]);

  const retry = useCallback(() => {
    setState({ status: 'running', progress: null });
    setAttempt((n) => n + 1);
  }, []);

  return { state, retry };
}
