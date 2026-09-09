"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, LabOut, ApiError } from "@/lib/api";

const DIFFICULTY_COLOR: Record<string, string> = {
  beginner: "text-success border-success/40 bg-success/10",
  intermediate: "text-amber border-amber/40 bg-amber/10",
  advanced: "text-danger border-danger/40 bg-danger/10",
};

export default function LabsPage() {
  const router = useRouter();
  const [labs, setLabs] = useState<LabOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setLabs(await api.listLabs());
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError("Não foi possível carregar os labs.");
      }
    })();
  }, [router]);

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6">
          <h1 className="text-xl text-ink">Labs</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Ambientes isolados e efêmeros — cada sessão expira automaticamente.
          </p>
        </header>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {labs.map((lab) => (
            <Link
              key={lab.id}
              href={`/labs/${lab.id}`}
              className="block rounded border border-border bg-panel p-5 transition-colors hover:border-trace/60"
            >
              <div className="flex items-start justify-between">
                <h2 className="text-base text-ink">{lab.name}</h2>
                <span
                  className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
                    DIFFICULTY_COLOR[lab.difficulty] ?? "text-ink-muted border-border"
                  }`}
                >
                  {lab.difficulty}
                </span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{lab.description}</p>
              <div className="mt-4 flex items-center justify-between font-mono text-xs text-ink-muted">
                <span>{lab.category}</span>
                <span>~{lab.estimated_minutes} min</span>
              </div>
            </Link>
          ))}

          {labs.length === 0 && !error && (
            <p className="text-sm text-ink-muted">Nenhum lab publicado ainda.</p>
          )}
        </div>
      </main>
    </div>
  );
}
