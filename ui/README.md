# chessreview — interfaccia

React 19 + TypeScript + Vite, con Tailwind 4 e chessground per la scacchiera.

## Avvio in sviluppo

Serve il backend acceso, dalla radice del progetto:

```bash
uvicorn chessreview.api.app:app --reload
```

Poi, da questa cartella:

```bash
npm install
npm run dev
```

Vite inoltra le chiamate a `/api` verso `http://localhost:8000` (vedi `vite.config.ts`).

## Struttura

- `src/api/` — tipi dello schema del backend e l'unico client HTTP/SSE
- `src/lib/` — formattazione, stile delle categorie di mossa, stato derivato della review
- `src/hooks/` — analisi in streaming, scorciatoie da tastiera, misura degli elementi
- `src/components/` — elenco partite, scacchiera, grafico, riepilogo, formulario

## Scorciatoie

← e → scorrono le mosse, Home e Fine vanno all'inizio e alla fine, F gira la scacchiera.
