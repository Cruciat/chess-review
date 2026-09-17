import type { GameMeta, PlayerProfile, RatingStats } from '../api/types';

interface PlayerCardProps {
  profile: PlayerProfile;
  /** Le partite caricate: da qui l'andamento recente del rating. */
  games: GameMeta[];
}

const TIME_CLASS_LABEL: Record<RatingStats['timeClass'], string> = {
  rapid: 'Rapid',
  blitz: 'Blitz',
  bullet: 'Bullet',
  daily: 'Giornaliere',
};

const monthYear = new Intl.DateTimeFormat('it-IT', { month: 'long', year: 'numeric' });

function countryName(code: string): string {
  try {
    return new Intl.DisplayNames(['it'], { type: 'region' }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** Bandiera come emoji, dalle due lettere del codice ISO. */
function flag(code: string): string {
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 127397 + c.charCodeAt(0)));
}

/** Il rating del giocatore partita dopo partita, dalla più vecchia. */
function ratingHistory(games: GameMeta[], username: string, timeClass: string): number[] {
  const me = username.toLowerCase();
  return games
    .filter((g) => g.timeClass === timeClass)
    .sort((a, b) => a.playedAt.localeCompare(b.playedAt))
    .map((g) => (g.white.username.toLowerCase() === me ? g.white.rating : g.black.rating))
    .filter((r): r is number => r !== null);
}

function Sparkline({ values }: { values: number[] }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const points = values.map((v, i) => `${(i / (values.length - 1)) * 100},${28 - ((v - min) / span) * 24}`).join(' ');
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="mt-3 block h-8 w-full" aria-hidden>
      <polyline points={points} fill="none" className="stroke-paper/70" strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

function RatingTile({ stats, history }: { stats: RatingStats; history: number[] }) {
  const total = stats.wins + stats.draws + stats.losses;
  const share = (n: number) => (total ? `${(100 * n) / total}%` : '0%');

  return (
    <div className="flex flex-col bg-deck px-4 py-3">
      <p className="text-sm text-muted">{TIME_CLASS_LABEL[stats.timeClass]}</p>
      <p className="font-display text-4xl font-semibold leading-tight tabular-nums">{stats.rating ?? '–'}</p>
      {stats.best !== null && <p className="text-sm tabular-nums text-muted">massimo {stats.best}</p>}

      {total > 0 && (
        <div className="mt-3">
          <div className="flex h-1.5 overflow-hidden rounded-full bg-rule" aria-hidden>
            <span className="bg-paper" style={{ width: share(stats.wins) }} />
            <span className="bg-muted/60" style={{ width: share(stats.draws) }} />
          </div>
          <p className="mt-1.5 text-xs tabular-nums text-muted">
            {stats.wins} vinte, {stats.draws} patte, {stats.losses} perse
          </p>
        </div>
      )}

      {history.length >= 3 && (
        <div className="mt-auto" title={`Rating nelle ultime ${history.length} partite ${TIME_CLASS_LABEL[stats.timeClass].toLowerCase()}`}>
          <Sparkline values={history} />
        </div>
      )}
    </div>
  );
}

/** Intestazione dell'elenco: chi è il giocatore e come va nelle varie cadenze. */
export default function PlayerCard({ profile, games }: PlayerCardProps) {
  const displayName = profile.url ? decodeURIComponent(profile.url.split('/').pop() ?? profile.username) : profile.username;
  const joined = profile.joined ? monthYear.format(new Date(profile.joined)) : null;

  return (
    <section className="mb-10">
      <div className="flex items-center gap-5">
        {profile.avatar ? (
          <img src={profile.avatar} alt="" className="size-20 shrink-0 rounded-[3px] bg-deck object-cover sm:size-24" />
        ) : (
          <span className="flex size-20 shrink-0 items-center justify-center rounded-[3px] bg-deck font-display text-4xl text-muted sm:size-24">
            {displayName.charAt(0).toUpperCase()}
          </span>
        )}
        <div className="min-w-0">
          <h1 className="flex items-baseline gap-3 font-display text-4xl font-semibold leading-tight sm:text-5xl">
            {profile.title && <span className="rounded-[3px] bg-paper px-1.5 text-2xl text-ink">{profile.title}</span>}
            <span className="truncate">{displayName}</span>
          </h1>
          <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-muted">
            {profile.name && profile.name.toLowerCase() !== displayName.toLowerCase() && <span className="text-paper">{profile.name}</span>}
            {profile.country && (
              <span>
                <span aria-hidden className="mr-1.5">
                  {flag(profile.country)}
                </span>
                {countryName(profile.country)}
              </span>
            )}
            {joined && <span>Su chess.com da {joined}</span>}
            {profile.league && <span>Lega {profile.league}</span>}
          </p>
        </div>
      </div>

      {profile.ratings.length > 0 && (
        <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-[3px] bg-rule md:grid-cols-4">
          {profile.ratings.map((stats) => (
            <RatingTile key={stats.timeClass} stats={stats} history={ratingHistory(games, profile.username, stats.timeClass)} />
          ))}
        </div>
      )}
    </section>
  );
}
