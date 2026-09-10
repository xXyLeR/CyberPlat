"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Estado do segundo fator (MFA) — só aparece se o backend responder
  // mfa_required=true depois da primeira etapa (email+senha).
  const [mfaPendingToken, setMfaPendingToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        const result = await api.login(email, password);
        if (result.mfa_required && result.mfa_pending_token) {
          setMfaPendingToken(result.mfa_pending_token);
        } else if (result.access_token) {
          setToken(result.access_token);
          router.push("/dashboard");
        }
      } else {
        const result = await api.register(email, password);
        setToken(result.access_token);
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível conectar à API");
    } finally {
      setLoading(false);
    }
  }

  async function handleMfaSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!mfaPendingToken) return;
    setError(null);
    setLoading(true);
    try {
      const result = await api.mfaLoginVerify(mfaPendingToken, mfaCode);
      if (result.access_token) {
        setToken(result.access_token);
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Código inválido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-1 md:grid-cols-[1.2fr_1fr]">
      {/* Painel esquerdo — identidade, não um hero genérico com gradiente */}
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-panel p-10 md:flex">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-trace shadow-[0_0_8px_2px_rgba(79,216,232,0.6)]" />
          <span className="font-mono text-sm text-ink">vantage_range</span>
        </div>

        <div className="max-w-md">
          <p className="font-mono text-xs uppercase tracking-wide text-trace">
            cyber_range // ambiente isolado
          </p>
          <h1 className="mt-3 text-3xl leading-tight text-ink">
            Pratique Pentest, Red Team e Cloud Security em ambientes controlados e efêmeros.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-ink-muted">
            Cada laboratório roda em rede isolada, com recursos limitados e destruição automática
            ao final da sessão. Nenhum exercício aqui alcança sistemas fora da plataforma.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4 font-mono text-xs text-ink-muted">
          <div>
            <div className="text-ink">04</div>
            <div>categorias</div>
          </div>
          <div>
            <div className="text-ink">isolado</div>
            <div>por padrão</div>
          </div>
          <div>
            <div className="text-ink">efêmero</div>
            <div>expira sozinho</div>
          </div>
        </div>
      </div>

      {/* Painel direito — formulário */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {mfaPendingToken ? (
            <>
              <h2 className="text-xl text-ink">Verificação em duas etapas</h2>
              <p className="mt-1 text-sm text-ink-muted">
                Digite o código de 6 dígitos do seu app autenticador.
              </p>
              <form onSubmit={handleMfaSubmit} className="mt-6 space-y-4">
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  className="w-full rounded border border-border bg-panel px-3 py-2 text-center font-mono text-lg tracking-widest text-ink outline-none focus:border-trace"
                  placeholder="000000"
                />
                {error && (
                  <p className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded bg-trace px-3 py-2 text-sm font-medium text-base hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? "Verificando..." : "Confirmar"}
                </button>
              </form>
              <button
                onClick={() => {
                  setMfaPendingToken(null);
                  setMfaCode("");
                  setError(null);
                }}
                className="mt-4 text-sm text-ink-muted hover:text-trace"
              >
                Voltar
              </button>
            </>
          ) : (
            <>
              <h2 className="text-xl text-ink">
                {mode === "login" ? "Entrar na plataforma" : "Criar conta"}
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                {mode === "login"
                  ? "Use suas credenciais para acessar seus laboratórios."
                  : "Novas contas começam com o papel de aluno."}
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label className="mb-1 block text-xs text-ink-muted">Email</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded border border-border bg-panel px-3 py-2 text-sm text-ink outline-none focus:border-trace"
                    placeholder="voce@empresa.com"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-ink-muted">Senha</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded border border-border bg-panel px-3 py-2 text-sm text-ink outline-none focus:border-trace"
                    placeholder="mínimo 8 caracteres"
                  />
                </div>

                {error && (
                  <p className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded bg-trace px-3 py-2 text-sm font-medium text-base transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? "Processando..." : mode === "login" ? "Entrar" : "Criar conta"}
                </button>
              </form>

              <button
                onClick={() => setMode(mode === "login" ? "register" : "login")}
                className="mt-4 text-sm text-ink-muted hover:text-trace"
              >
                {mode === "login" ? "Ainda não tem conta? Criar uma" : "Já tem conta? Entrar"}
              </button>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
