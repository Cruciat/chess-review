interface BoardControlsProps {
  atStart: boolean;
  atEnd: boolean;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
  onFlip: () => void;
}

const ICONS = {
  first: 'M6 5v14M18 5l-8 7 8 7',
  prev: 'M15 5l-7 7 7 7',
  next: 'M9 5l7 7-7 7',
  last: 'M18 5v14M6 5l8 7-8 7',
  flip: 'M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3',
};

function Icon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={path} />
    </svg>
  );
}

const button =
  'flex h-10 items-center justify-center rounded-[3px] text-paper transition-colors hover:bg-rule disabled:text-muted/40 disabled:hover:bg-transparent';

export default function BoardControls({ atStart, atEnd, onFirst, onPrev, onNext, onLast, onFlip }: BoardControlsProps) {
  return (
    <div className="flex items-center gap-1">
      <div className="grid flex-1 grid-cols-4 gap-1">
        <button type="button" className={button} onClick={onFirst} disabled={atStart} aria-label="Posizione iniziale" title="Posizione iniziale (Home)">
          <Icon path={ICONS.first} />
        </button>
        <button type="button" className={button} onClick={onPrev} disabled={atStart} aria-label="Mossa precedente" title="Mossa precedente (←)">
          <Icon path={ICONS.prev} />
        </button>
        <button type="button" className={button} onClick={onNext} disabled={atEnd} aria-label="Mossa successiva" title="Mossa successiva (→)">
          <Icon path={ICONS.next} />
        </button>
        <button type="button" className={button} onClick={onLast} disabled={atEnd} aria-label="Posizione finale" title="Posizione finale (Fine)">
          <Icon path={ICONS.last} />
        </button>
      </div>
      <button type="button" className={`${button} w-12`} onClick={onFlip} aria-label="Gira la scacchiera" title="Gira la scacchiera (F)">
        <Icon path={ICONS.flip} />
      </button>
    </div>
  );
}
