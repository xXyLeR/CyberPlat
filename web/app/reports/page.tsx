"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { api, ReportOut, ApiError } from "@/lib/api";

const SEVERITY_COLOR: Record<string, string> = {
  Crítica: "text-danger border-danger/40 bg-danger/10",
  Alta: "text-amber border-amber/40 bg-amber/10",
  Média: "text-trace border-trace/40 bg-trace/10",
  Baixa: "text-ink-muted border-border",
};

export default function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<ReportOut[]>([]);
  const [selected, setSelected] = useState<ReportOut | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const list = await api.listMyReports();
      setReports(list);
      if (list.length > 0 && !selected) setSelected(list[0]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError("Não foi possível carregar os relatórios.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const report = await api.generateReport("Relatório de Pentest");
      setReports([report, ...reports]);
      setSelected(report);
    } catch {
      setError("Não foi possível gerar o relatório.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl text-ink">Reports</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Snapshot dos exercícios resolvidos, no formato de um relatório de pentest.
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="rounded bg-trace px-4 py-2 text-sm font-medium text-base hover:opacity-90 disabled:opacity-50"
          >
            {generating ? "Gerando..." : "Gerar novo relatório"}
          </button>
        </header>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="space-y-2 lg:col-span-1">
            {reports.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className={`block w-full rounded border p-3 text-left text-sm ${
                  selected?.id === r.id
                    ? "border-trace/60 bg-panel-raised text-ink"
                    : "border-border bg-panel text-ink-muted hover:border-trace/40"
                }`}
              >
                <p className="text-ink">{r.title}</p>
                <p className="mt-1 font-mono text-xs text-ink-muted">
                  {new Date(r.generated_at).toLocaleString("pt-BR")}
                </p>
              </button>
            ))}
            {reports.length === 0 && (
              <p className="text-sm text-ink-muted">Nenhum relatório gerado ainda.</p>
            )}
          </div>

          {selected && (
            <div className="space-y-4 rounded border border-border bg-panel p-6 lg:col-span-2">
              <div>
                <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                  executive summary
                </p>
                <p className="mt-1 text-sm leading-relaxed text-ink">
                  {selected.content.executive_summary}
                </p>
              </div>

              <div>
                <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">scope</p>
                <p className="mt-1 text-sm text-ink-muted">{selected.content.scope}</p>
              </div>

              <div>
                <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                  findings
                </p>
                <div className="mt-2 space-y-2">
                  {selected.content.findings.map((f, idx) => (
                    <div key={idx} className="rounded border border-border bg-panel-raised p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm text-ink">{f.title}</p>
                        <span
                          className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
                            SEVERITY_COLOR[f.severity] ?? "text-ink-muted border-border"
                          }`}
                        >
                          {f.severity}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-ink-muted">{f.evidence}</p>
                    </div>
                  ))}
                  {selected.content.findings.length === 0 && (
                    <p className="text-sm text-ink-muted">Nenhum finding neste relatório.</p>
                  )}
                </div>
              </div>

              <div>
                <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                  conclusion
                </p>
                <p className="mt-1 text-sm text-ink-muted">{selected.content.conclusion}</p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
