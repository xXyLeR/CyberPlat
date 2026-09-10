"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, TeamOut, ApiError } from "@/lib/api";

export default function TeamsPage() {
  const router = useRouter();
  const [teams, setTeams] = useState<TeamOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setTeams(await api.listTeams());
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          setError("Seu papel não tem acesso à gestão de teams.");
          return;
        }
        setError("Não foi possível carregar os teams.");
      }
    })();
  }, [router]);

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6">
          <h1 className="text-xl text-ink">Teams</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Times da sua organização — gerenciados por Org Admins e Team Managers.
          </p>
        </header>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {teams.map((team) => (
            <div key={team.id} className="rounded border border-border bg-panel p-5">
              <h2 className="text-base text-ink">{team.name}</h2>
            </div>
          ))}
          {teams.length === 0 && !error && (
            <p className="text-sm text-ink-muted">Nenhum team criado ainda.</p>
          )}
        </div>
      </main>
    </div>
  );
}
