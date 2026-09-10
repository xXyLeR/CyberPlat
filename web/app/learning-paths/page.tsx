"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, LearningPathOut, ApiError } from "@/lib/api";

export default function LearningPathsPage() {
  const router = useRouter();
  const [paths, setPaths] = useState<LearningPathOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setPaths(await api.listLearningPaths());
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError("Não foi possível carregar as trilhas.");
      }
    })();
  }, [router]);

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6">
          <h1 className="text-xl text-ink">Learning Paths</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Trilhas estruturadas combinando teoria, quizzes e prática guiada.
          </p>
        </header>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {paths.map((path) => (
            <Link
              key={path.id}
              href={`/learning-paths/${path.id}`}
              className="block rounded border border-border bg-panel p-5 transition-colors hover:border-trace/60"
            >
              <h2 className="text-base text-ink">{path.title}</h2>
              <p className="mt-2 line-clamp-3 text-sm text-ink-muted">{path.description}</p>
            </Link>
          ))}

          {paths.length === 0 && !error && (
            <p className="text-sm text-ink-muted">Nenhuma trilha publicada ainda.</p>
          )}
        </div>
      </main>
    </div>
  );
}
