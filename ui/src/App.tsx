import { useState, useRef } from 'react';
import Board from './components/Board';
import AdvantageChart from './components/AdvantageChart';

// Interfacce basate sugli schemi del tuo backend
interface GameMeta {
  id: string;
  url: string;
  white: { username: string; rating: number; result: string };
  black: { username: string; rating: number; result: string };
  playedAt: string;
  timeClass: string;
  yourOutcome?: string;
}

interface MoveAnalysis {
  ply: number;
  moveNumber: number;
  turn: 'white' | 'black';
  san: string;
  fenBefore: string;
  fenAfter: string;
  whiteWinPercent: number;
  classification: string;
  label: string;
  isMistake: boolean;
  isNotable: boolean;
}

export default function App() {
  const [username, setUsername] = useState('');
  const [games, setGames] = useState<GameMeta[]>([]);
  const [loadingGames, setLoadingGames] = useState(false);
  
  const [selectedGame, setSelectedGame] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 100 });
  const [moves, setMoves] = useState<MoveAnalysis[] | null>(null);
  const [currentPly, setCurrentPly] = useState(0);
  const [error, setError] = useState('');

  const eventSourceRef = useRef<EventSource | null>(null);

  // 1. Cerca le partite dell'utente (popola la cache del backend)
  const fetchGames = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;
    
    setLoadingGames(true);
    setError('');
    setGames([]);
    setMoves(null);
    setSelectedGame(null);

    try {
      const res = await fetch(`http://localhost:8000/api/games?username=${encodeURIComponent(username)}`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Errore nel recupero delle partite');
      }
      const data = await res.json();
      setGames(data.games);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoadingGames(false);
    }
  };

  // 2. Analizza la partita selezionata
  const startAnalysis = (gameUrl: string) => {
    setSelectedGame(gameUrl);
    setError('');
    setMoves(null);
    setCurrentPly(0);
    setProgress({ done: 0, total: 100 });
    setAnalyzing(true);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `http://localhost:8000/api/analyse/${encodeURIComponent(gameUrl)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('progress', (event) => {
      const data = JSON.parse(event.data);
      setProgress({ done: data.done, total: data.total });
    });

    es.addEventListener('result', (event) => {
      const data = JSON.parse(event.data);
      setMoves(data.moves);
      setAnalyzing(false);
      es.close();
    });

    es.addEventListener('error', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setError(data.message || 'Errore di connessione al backend');
      } catch {
        setError('Errore di comunicazione con il server Stockfish');
      }
      setAnalyzing(false);
      es.close();
    });
  };

  const currentMove = moves ? moves[currentPly] : null;
  const currentFen = currentMove 
    ? (currentMove.ply === 0 ? currentMove.fenBefore : currentMove.fenAfter) 
    : "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  return (
    <div className="min-h-screen bg-gray-100 p-8 text-gray-800">
      <header className="mb-8 max-w-6xl mx-auto flex gap-4 items-center">
        <h1 className="text-3xl font-bold text-gray-900 shrink-0">Analisi Partita</h1>
        
        {/* Barra di ricerca per Username */}
        <form onSubmit={fetchGames} className="flex-1 flex gap-2">
          <input 
            type="text" 
            placeholder="Il tuo username su chess.com (es: cruciat)" 
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={loadingGames || analyzing}
          />
          <button 
            type="submit" 
            disabled={loadingGames || analyzing}
            className="bg-gray-800 hover:bg-gray-900 text-white font-semibold py-2 px-6 rounded-lg shadow disabled:opacity-50 transition-colors"
          >
            {loadingGames ? 'Cerco...' : 'Trova Partite'}
          </button>
        </form>
      </header>

      <main className="mx-auto max-w-6xl grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Colonna Sinistra: Errori, Lista Partite o Scacchiera */}
        <section className="col-span-1 lg:col-span-2 flex flex-col gap-4">
          {error && (
            <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded shadow">
              <p className="font-bold">Errore</p>
              <p>{error}</p>
            </div>
          )}

          {/* Lista partite se non è stata selezionata un'analisi */}
          {games.length > 0 && !selectedGame && (
            <div className="bg-white p-6 rounded-lg shadow">
              <h2 className="text-xl font-bold mb-4">Le tue ultime partite</h2>
              <div className="flex flex-col gap-2 max-h-[600px] overflow-y-auto">
                {games.map(game => (
                  <button
                    key={game.id}
                    onClick={() => startAnalysis(game.url)}
                    className="flex justify-between items-center p-3 border border-gray-200 rounded hover:bg-blue-50 text-left transition-colors"
                  >
                    <div>
                      <p className="font-semibold">{game.white.username} ({game.white.rating}) vs {game.black.username} ({game.black.rating})</p>
                      <p className="text-sm text-gray-500">{new Date(game.playedAt).toLocaleDateString()} • {game.timeClass}</p>
                    </div>
                    <span className="bg-blue-600 text-white text-sm px-3 py-1 rounded">Analizza</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Barra di caricamento e Scacchiera (visibili quando si seleziona una partita) */}
          {selectedGame && (
            <>
              {analyzing && (
                <div className="bg-white p-6 rounded-lg shadow flex flex-col gap-3">
                  <div className="flex justify-between text-sm font-medium text-gray-600">
                    <span>Stockfish sta calcolando...</span>
                    <span>{progress.done} / {progress.total} mosse</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div 
                      className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out" 
                      style={{ width: `${Math.max(5, (progress.done / progress.total) * 100)}%` }}
                    ></div>
                  </div>
                </div>
              )}

              <div className="flex justify-center items-start bg-white p-6 rounded-lg shadow">
                <Board fen={currentFen} />
              </div>
            </>
          )}
        </section>

        {/* Colonna Destra: Grafico e Mosse (visibili solo se c'è un'analisi attiva) */}
        <section className="col-span-1 flex flex-col gap-6">
          <div className="bg-white p-4 rounded-lg shadow h-48 border border-gray-200">
            {moves ? (
              <AdvantageChart 
                data={moves} 
                onMoveSelect={(ply) => setCurrentPly(ply)} 
              />
            ) : (
              <div className="h-full w-full flex items-center justify-center text-gray-400 text-sm text-center px-4">
                Seleziona una partita per visualizzare il grafico del vantaggio.
              </div>
            )}
          </div>

          <div className="bg-white p-4 rounded-lg shadow flex-1 overflow-y-auto border border-gray-200 max-h-[600px]">
            <h3 className="font-semibold text-lg mb-4">Registro Mosse</h3>
            <div className="flex flex-col gap-1">
              {!moves && (
                 <p className="text-gray-400 text-sm text-center mt-8">Nessuna mossa da mostrare.</p>
              )}
              {moves?.map((move) => (
                <button
                  key={move.ply}
                  className={`text-left px-3 py-2 rounded transition-colors flex justify-between items-center ${
                    currentPly === move.ply ? 'bg-blue-100 text-blue-800 font-medium' : 'hover:bg-gray-100'
                  }`}
                  onClick={() => setCurrentPly(move.ply)}
                >
                  <span>
                    {move.ply === 0 ? 'Inizio' : `${move.turn === 'white' ? move.moveNumber + '.' : move.moveNumber + '...'} ${move.san}`}
                  </span>
                  
                  {move.isNotable && (
                    <span className={`text-xs px-2 py-1 rounded font-bold ${move.isMistake ? 'bg-red-200 text-red-800' : 'bg-teal-200 text-teal-800'}`}>
                      {move.label}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
