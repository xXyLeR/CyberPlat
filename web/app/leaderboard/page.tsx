"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, LeaderboardEntryOut, TeamLeaderboardEntryOut, ApiError } from "@/lib/api";

export default function LeaderboardPage() {
  const router = useRouter();
  const [view, setView] = useState<"individual" | "teams">("individual");
  const [individual, setIndividual] = useState<LeaderboardEntryOut[]>([]);
  const [teams, setTeams] = useState<TeamLeaderboardEntryOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [ind, tm] = await Promise.all([api.individualLeaderboard(), api.teamLeaderboard()]);
        setIndividual(ind);
        setTeams(tm);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError("Não foi possível carregar o leaderboard.");
      }
    })();
  }, [router]);

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6">
          <h1 className="text-xl text-ink">Leaderboard</h1>
          <p className="mt-1 text-sm text-ink-muted">Ranking por XP, escopado à sua organização.</p>
        </header>

        <div className="mb-5 flex gap-2">
          <button
            onClick={() => setView("individual")}
            className={`rounded px-3 py-1.5 text-sm ${
              view === "individual" ? "bg-panel-raised text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            Individual
          </button>
          <button
            onClick={() => setView("teams")}
            className={`rounded px-3 py-1.5 text-sm ${
              view === "teams" ? "bg-panel-raised text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            Equipes
          </button>
        </div>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="overflow-hidden rounded border border-border bg-panel">
          {view === "individual"
            ? individual.map((entry) => (
                <div
                  key={entry.email}
                  className="flex items-center justify-between border-b border-border px-4 py-3 last:border-0"
                >
                  <div className="flex items-center gap-4">
                    <span className="w-6 font-mono text-sm text-ink-muted">#{entry.rank}</span>
                    <span className="text-sm text-ink">{entry.email}</span>
                  </div>
                  <div className="flex items-center gap-4 font-mono text-xs text-ink-muted">
                    <span>nível {entry.level}</span>
                    <span className="text-trace">{entry.xp} XP</span>
                  </div>
                </div>
              ))
            : teams.map((entry) => (
                <div
                  key={entry.team_name}
                  className="flex items-center justify-between border-b border-border px-4 py-3 last:border-0"
                >
                  <div className="flex items-center gap-4">
                    <span className="w-6 font-mono text-sm text-ink-muted">#{entry.rank}</span>
                    <span className="text-sm text-ink">{entry.team_name}</span>
                  </div>
                  <div className="flex items-center gap-4 font-mono text-xs text-ink-muted">
                    <span>{entry.member_count} membros</span>
                    <span className="text-trace">{entry.total_xp} XP</span>
                  </div>
                </div>
              ))}

          {view === "individual" && individual.length === 0 && !error && (
            <p className="px-4 py-6 text-sm text-ink-muted">Ninguém no ranking ainda.</p>
          )}
          {view === "teams" && teams.length === 0 && !error && (
            <p className="px-4 py-6 text-sm text-ink-muted">Nenhuma equipe com membros ainda.</p>
          )}
        </div>
      </main>
    </div>
  );
}
