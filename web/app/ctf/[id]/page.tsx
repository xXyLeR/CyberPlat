"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, ChallengeDetailOut, ApiError } from "@/lib/api";

export default function ChallengeDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const challengeId = params.id;

  const [challenge, setChallenge] = useState<ChallengeDetailOut | null>(null);
  const [flagValue, setFlagValue] = useState("");
  const [revealedHints, setRevealedHints] = useState(0);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setChallenge(await api.getChallenge(challengeId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError("Desafio não encontrado.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challengeId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await api.submitChallengeFlag(challengeId, flagValue);
      if (result.correct) {
        setFeedback({ type: "success", text: `Flag correta! +${result.points_awarded} XP` });
        setFlagValue("");
        load();
      } else {
        setFeedback({ type: "error", text: "Flag incorreta. Tente novamente." });
      }
    } catch (err) {
      setFeedback({
        type: "error",
        text: err instanceof ApiError ? err.message : "Falha ao submeter a flag.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <div className="flex">
        <Sidebar />
        <main className="min-h-screen flex-1 bg-base p-8">
          <p className="text-sm text-danger">{error}</p>
        </main>
      </div>
    );
  }

  if (!challenge) {
    return (
      <div className="flex">
        <Sidebar />
        <main className="min-h-screen flex-1 bg-base p-8">
          <p className="text-sm text-ink-muted">Carregando...</p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6 max-w-2xl">
          <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
            {challenge.category} · {challenge.difficulty} · {challenge.points} pts
          </p>
          <h1 className="mt-1 text-xl text-ink">{challenge.title}</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">{challenge.description}</p>
        </header>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <section className="rounded border border-border bg-panel p-6 lg:col-span-2">
            {challenge.solved ? (
              <p className="rounded border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
                Você já resolveu este desafio.
              </p>
            ) : (
              <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                  value={flagValue}
                  onChange={(e) => setFlagValue(e.target.value)}
                  placeholder="FLAG{...}"
                  className="flex-1 rounded border border-border bg-panel-raised px-3 py-2 font-mono text-sm text-ink outline-none focus:border-trace"
                />
                <button
                  type="submit"
                  disabled={submitting || !flagValue}
                  className="rounded bg-trace px-4 py-2 text-sm font-medium text-base hover:opacity-90 disabled:opacity-50"
                >
                  Submeter
                </button>
              </form>
            )}

            {feedback && (
              <p
                className={`mt-4 rounded border px-3 py-2 text-sm ${
                  feedback.type === "success"
                    ? "border-success/40 bg-success/10 text-success"
                    : "border-danger/40 bg-danger/10 text-danger"
                }`}
              >
                {feedback.text}
              </p>
            )}
          </section>

          <section className="rounded border border-border bg-panel p-5">
            <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">hints</p>
            <div className="mt-2 space-y-2">
              {challenge.hints.slice(0, revealedHints).map((hint, idx) => (
                <p key={idx} className="text-sm text-ink-muted">
                  {hint}
                </p>
              ))}
              {revealedHints < challenge.hints.length && (
                <button
                  onClick={() => setRevealedHints(revealedHints + 1)}
                  className="text-sm text-trace hover:underline"
                >
                  Revelar hint {revealedHints + 1}/{challenge.hints.length}
                </button>
              )}
              {challenge.hints.length === 0 && (
                <p className="text-sm text-ink-muted">Nenhum hint disponível.</p>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
