"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, ChallengeOut, ApiError } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  web: "Web",
  network: "Network",
  linux: "Linux",
  windows: "Windows",
  active_directory: "Active Directory",
  cloud: "Cloud",
  containers: "Containers",
  cryptography: "Cryptography",
  forensics: "Forensics",
  reverse_engineering: "Reverse Engineering",
};

export default function CtfPage() {
  const router = useRouter();
  const [challenges, setChallenges] = useState<ChallengeOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setChallenges(await api.listChallenges());
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError("Não foi possível carregar os desafios.");
      }
    })();
  }, [router]);

  const byCategory = challenges.reduce<Record<string, ChallengeOut[]>>((acc, c) => {
    (acc[c.category] ??= []).push(c);
    return acc;
  }, {});

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl text-ink">CTF</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Desafios isolados por categoria — encontre a flag, submeta, pontue.
            </p>
          </div>
          <Link
            href="/leaderboard"
            className="rounded border border-trace/40 bg-trace/10 px-4 py-2 text-sm text-trace hover:bg-trace/20"
          >
            Ver leaderboard
          </Link>
        </header>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="space-y-8">
          {Object.entries(byCategory).map(([category, items]) => (
            <section key={category}>
              <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-ink-muted">
                {CATEGORY_LABELS[category] ?? category}
              </h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {items.map((c) => (
                  <Link
                    key={c.id}
                    href={`/ctf/${c.id}`}
                    className={`block rounded border p-4 transition-colors ${
                      c.solved
                        ? "border-success/40 bg-success/5"
                        : "border-border bg-panel hover:border-trace/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm text-ink">{c.title}</h3>
                      {c.solved && <span className="text-xs text-success">✓</span>}
                    </div>
                    <div className="mt-2 flex items-center justify-between font-mono text-xs text-ink-muted">
                      <span>{c.difficulty}</span>
                      <span>{c.points} pts</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}

          {challenges.length === 0 && !error && (
            <p className="text-sm text-ink-muted">Nenhum desafio publicado ainda.</p>
          )}
        </div>
      </main>
    </div>
  );
}
