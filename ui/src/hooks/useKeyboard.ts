import { useEffect, useRef } from 'react';

/**
 * Scorciatoie da tastiera globali, per nome del tasto (KeyboardEvent.key).
 * Ignorate mentre si scrive in un campo di testo, e con i modificatori
 * premuti per non rubare le scorciatoie del browser.
 */
export function useKeyboard(bindings: Record<string, () => void>, enabled = true) {
  const current = useRef(bindings);

  useEffect(() => {
    current.current = bindings;
  });

  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }
      const action = current.current[event.key];
      if (action) {
        event.preventDefault();
        action();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [enabled]);
}
