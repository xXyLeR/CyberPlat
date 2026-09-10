"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ProgressBar } from "@/components/ProgressBar";
import { api, UserOut, LabOut, AchievementOut, ApiError } from "@/lib/api";

const XP_PER_LEVEL = 500;

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserOut | null>(null);
  const [labs, setLabs] = useState<LabOut[]>([]);
  const [achievements, setAchievements] = useState<AchievementOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [me, labList, myAchievements] = await Promise.all([
          api.me(),
          api.listLabs(),
          api.myAchievements(),
        ]);
        setUser(me);
        setLabs(labList);
        setAchievements(myAchievements);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        setError("Não foi possível carregar o dashboard. Verifique se o core-api está rodando.");
      }
    })();
  }, [router]);

  const xpIntoLevel = user ? user.xp % XP_PER_LEVEL : 0;
  const levelPercent = user ? Math.round((xpIntoLevel / XP_PER_LEVEL) * 100) : 0;

  // Categorias derivadas dos labs publicados. Até a Fase 3 (Learning
  // Paths com progresso granular), o "percentual concluído por
  // categoria" real ainda não existe — mostramos apenas quantos labs
  // publicados existem por categoria, de forma honesta, sem inventar
  // uma métrica de progresso que não temos ainda.
  const categoryCounts = labs.reduce<Record<string, number>>((acc, lab) => {
    acc[lab.category] = (acc[lab.category] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex">
      <Sidebar />
      <main className="min-h-screen flex-1 bg-base p-8">
        <header className="mb-8">
          <h1 className="text-xl text-ink">Dashboard</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {user ? user.email : "carregando..."}
          </p>
        </header>

        {error && (
          <p className="mb-6 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* Painel principal: Level + XP — o "hero" real do dashboard */}
          <section className="rounded border border-border bg-panel p-6 lg:col-span-2">
            <div className="flex items-end justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                  nível atual
                </p>
                <p className="mt-1 font-mono text-4xl text-ink">
                  {user ? user.level : "--"}
                </p>
              </div>
              <div className="text-right">
                <p className="font-mono text-xs text-ink-muted">XP total</p>
                <p className="font-mono text-lg text-trace">{user ? user.xp : 0}</p>
              </div>
            </div>

            <div className="mt-6">
              <ProgressBar
                label={`Progresso para o nível ${user ? user.level + 1 : "--"}`}
                percent={levelPercent}
              />
            </div>

            <div className="mt-8 space-y-4">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                labs publicados por categoria
              </p>
              {Object.keys(categoryCounts).length === 0 && (
                <p className="text-sm text-ink-muted">Nenhum lab publicado ainda.</p>
              )}
              {Object.entries(categoryCounts).map(([category, count]) => (
                <ProgressBar
                  key={category}
                  label={category}
                  percent={Math.min(100, count * 25)}
                  colorClass="bg-success"
                />
              ))}
            </div>
          </section>

          {/* Coluna lateral: atalhos + resumo */}
          <section className="space-y-5">
            <div className="rounded border border-border bg-panel p-5">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                labs disponíveis
              </p>
              <p className="mt-1 font-mono text-3xl text-ink">{labs.length}</p>
              <a
                href="/labs"
                className="mt-3 inline-block text-sm text-trace hover:underline"
              >
                Ver todos os labs
              </a>
            </div>

            <div className="rounded border border-border bg-panel p-5">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                seu papel
              </p>
              <p className="mt-1 text-lg text-ink">
                {user?.role === "student" && "Aluno"}
                {user?.role === "instructor" && "Instrutor"}
                {user?.role === "org_admin" && "Administrador"}
                {user?.role === "super_admin" && "Super Admin"}
              </p>
            </div>

            <div className="rounded border border-border bg-panel p-5">
              <p className="font-mono text-xs uppercase tracking-wide text-ink-muted">
                badges
              </p>
              {achievements.length === 0 && (
                <p className="mt-2 text-sm text-ink-muted">Nenhum badge ainda.</p>
              )}
              <div className="mt-2 space-y-2">
                {achievements.map((a) => (
                  <div key={a.badge.slug} className="flex items-center gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-amber" />
                    <span className="text-sm text-ink">{a.badge.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
