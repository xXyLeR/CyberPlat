"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, LabOut, LabSessionOut, ApiError } from "@/lib/api";

export default function LabDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const labId = params.id;

  const [lab, setLab] = useState<LabOut | null>(null);
  const [session, setSession] = useState<LabSessionOut | null>(null);
  const [flagValue, setFlagValue] = useState("");
  const [feedback, setFeedback] = useState<
    { type: "success" | "error" | "info"; text: string } | null
  >(null);
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setLab(await api.getLab(labId));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setFeedback({ type: "error", text: "Lab não encontrado." });
      }
    })();
  }, [labId, router]);

  async function handleStart() {
    setStarting(true);
    setFeedback(null);
    try {
      const newSession = await api.startLabSession(labId);
      setSession(newSession);
      setFeedback({ type: "info", text: "Ambiente provisionado. Boa sorte." });
    } catch (err) {
      setFeedback({
        type: "error",
        text: err instanceof ApiError ? err.message : "Falha ao iniciar o laboratório.",
      });
    } finally {
      setStarting(false);
    }
  }

  async function handleTerminate() {
    if (!session) return;
    await api.terminateLabSession(session.id);
    setSession({ ...session, status: "destroyed" });
    setFeedback({ type: "info", text: "Ambiente encerrado e destruído." });
  }

  async function handleSubmitFlag(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await api.submitFlag(session.id, flagValue);
      if (result.correct) {
        setFeedback({
          type: "success",
          text: `Flag correta! +${result.points_awarded} XP`,
        });
        setFlagValue("");
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

  if (!lab) {
    return (
      <div className="flex">
        <Sidebar />
        <main className="min-h-screen flex-1 bg-base p-8">
          {feedback ? (
            <p className="text-sm text-danger">{feedback.text}</p>
          ) : (
            <p className="text-sm text-ink-muted">Carregando...</p>
          )}
        </main>
      </div>
    );
  }

  const isRunning = session?.status === "running";

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6">
          <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
            {lab.category} · {lab.difficulty}
          </p>
          <h1 className="mt-1 text-xl text-ink">{lab.name}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
            {lab.description}
          </p>
        </header>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <section className="rounded border border-border bg-panel p-6 lg:col-span-2">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                sessão do laboratório
              </p>
              {session && (
                <span
                  className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
                    isRunning
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border text-ink-muted"
                  }`}
                >
                  {session.status}
                </span>
              )}
            </div>

            {!session && (
              <div className="mt-4">
                <button
                  onClick={handleStart}
                  disabled={starting}
                  className="rounded bg-trace px-4 py-2 text-sm font-medium text-base hover:opacity-90 disabled:opacity-50"
                >
                  {starting ? "Provisionando..." : "Iniciar laboratório"}
                </button>
                <p className="mt-2 text-xs text-ink-muted">
                  O ambiente expira automaticamente após o tempo limite definido no lab.
                </p>
              </div>
            )}

            {session && isRunning && (
              <div className="mt-4 space-y-4">
                <p className="font-mono text-xs text-ink-muted">
                  expira em: {session.expires_at ?? "n/d"}
                </p>

                {session.access_url && (
                  <a
                    href={`${process.env.NEXT_PUBLIC_SESSION_GATEWAY_URL ?? ""}${session.access_url}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block rounded border border-trace/40 bg-trace/10 px-4 py-2 text-sm text-trace hover:bg-trace/20"
                  >
                    Abrir laboratório em nova aba
                  </a>
                )}

                <form onSubmit={handleSubmitFlag} className="flex gap-2">
                  <input
                    value={flagValue}
                    onChange={(e) => setFlagValue(e.target.value)}
                    placeholder="VANTAGE{...}"
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

                <button
                  onClick={handleTerminate}
                  className="text-sm text-ink-muted hover:text-danger"
                >
                  Encerrar laboratório agora
                </button>
              </div>
            )}

            {feedback && (
              <p
                className={`mt-4 rounded border px-3 py-2 text-sm ${
                  feedback.type === "success"
                    ? "border-success/40 bg-success/10 text-success"
                    : feedback.type === "error"
                    ? "border-danger/40 bg-danger/10 text-danger"
                    : "border-trace/40 bg-trace/10 text-trace"
                }`}
              >
                {feedback.text}
              </p>
            )}
          </section>

          <section className="space-y-5">
            <div className="rounded border border-border bg-panel p-5">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                tempo estimado
              </p>
              <p className="mt-1 text-lg text-ink">{lab.estimated_minutes} min</p>
            </div>
            <div className="rounded border border-border bg-panel p-5">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                isolamento
              </p>
              <p className="mt-1 text-sm text-ink-muted">
                Rede dedicada, egress bloqueado por padrão, recursos limitados e destruição
                automática ao expirar.
              </p>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
