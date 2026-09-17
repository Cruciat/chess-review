import type { Progress } from '../api/types';

interface AnalysisProgressProps {
  progress: Progress | null;
}

function Bar({ label, share, detail, active }: { label: string; share: number; detail: string; active: boolean }) {
  return (
    <div>
      <div className={`flex justify-between text-sm ${active ? '' : 'text-muted'}`}>
        <span>{label}</span>
        <span className="tabular-nums">{detail}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-rule">
        <div className="h-full bg-paper transition-[width] duration-300 ease-out motion-reduce:transition-none" style={{ width: `${share}%` }} />
      </div>
    </div>
  );
}

/**
 * Le due passate dell'analisi, ognuna con la sua barra. Il totale della
 * seconda si conosce solo a fine scansione: un'unica barra tornerebbe
 * indietro al cambio di fase.
 */
export default function AnalysisProgress({ progress }: AnalysisProgressProps) {
  const scanning = progress?.phase === 'scan';
  const deep = progress?.phase === 'deep';

  return (
    <section aria-live="polite" className="space-y-4">
      <div>
        <p className="font-medium">Stockfish sta analizzando la partita</p>
        <p className="mt-1 text-sm text-muted">
          {progress === null
            ? 'In attesa del motore, che potrebbe essere occupato con un’altra partita.'
            : 'Prima una scansione veloce di tutte le posizioni, poi un riesame più profondo delle mosse sospette.'}
        </p>
      </div>
      <Bar
        label="Scansione"
        share={deep ? 100 : scanning ? (100 * progress.done) / progress.total : 0}
        detail={deep ? 'completata' : scanning ? `${progress.done} di ${progress.total}` : ''}
        active={scanning}
      />
      <Bar
        label="Riesame"
        share={deep ? (100 * progress.done) / progress.total : 0}
        detail={deep ? `${progress.done} di ${progress.total}` : ''}
        active={deep}
      />
    </section>
  );
}
