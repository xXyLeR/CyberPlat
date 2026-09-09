"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ProgressBar } from "@/components/ProgressBar";
import { api, CourseOut, LearningPathDetailOut, QuizQuestionOut, ApiError } from "@/lib/api";

function QuizBlock({ course, onCompleted }: { course: CourseOut; onCompleted: () => void }) {
  const [questions, setQuestions] = useState<QuizQuestionOut[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<{ score_percent: number; passed: boolean } | null>(null);
  const [open, setOpen] = useState(false);

  async function loadQuiz() {
    setOpen(true);
    if (!questions) setQuestions(await api.getCourseQuiz(course.id));
  }

  async function handleSubmit() {
    const res = await api.submitQuiz(course.id, answers);
    setResult({ score_percent: res.score_percent, passed: res.passed });
    if (res.course_completed) onCompleted();
  }

  if (!open) {
    return (
      <button
        onClick={loadQuiz}
        className="rounded border border-trace/40 bg-trace/10 px-3 py-1.5 text-xs text-trace hover:bg-trace/20"
      >
        {course.completed ? "Refazer quiz" : "Fazer quiz"}
      </button>
    );
  }

  return (
    <div className="mt-3 space-y-3 rounded border border-border bg-panel-raised p-4">
      {questions === null && <p className="text-sm text-ink-muted">Carregando...</p>}
      {questions?.map((q) => (
        <div key={q.id}>
          <p className="text-sm text-ink">{q.prompt}</p>
          <div className="mt-1 space-y-1">
            {q.options.map((option, idx) => (
              <label key={idx} className="flex items-center gap-2 text-sm text-ink-muted">
                <input
                  type="radio"
                  name={q.id}
                  checked={answers[q.id] === idx}
                  onChange={() => setAnswers({ ...answers, [q.id]: idx })}
                />
                {option}
              </label>
            ))}
          </div>
        </div>
      ))}

      {questions && (
        <button
          onClick={handleSubmit}
          className="rounded bg-trace px-3 py-1.5 text-xs font-medium text-base hover:opacity-90"
        >
          Enviar respostas
        </button>
      )}

      {result && (
        <p
          className={`text-sm ${result.passed ? "text-success" : "text-danger"}`}
        >
          {result.passed ? "Aprovado" : "Não atingiu a nota mínima"} — {result.score_percent}%
        </p>
      )}
    </div>
  );
}

export default function LearningPathDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const pathId = params.id;

  const [path, setPath] = useState<LearningPathDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      setPath(await api.getLearningPath(pathId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError("Não foi possível carregar a trilha.");
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathId]);

  async function handleCompleteTheory(courseId: string) {
    await api.completeTheoryCourse(courseId);
    reload();
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

  if (!path) {
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
          <h1 className="text-xl text-ink">{path.title}</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">{path.description}</p>
        </header>

        <div className="mb-8 max-w-md">
          <ProgressBar
            label={`${path.progress_completed}/${path.progress_total} cursos concluídos`}
            percent={path.progress_percent}
          />
        </div>

        <div className="space-y-3">
          {path.courses.map((course) => (
            <div
              key={course.id}
              className="rounded border border-border bg-panel p-5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-base text-ink">{course.title}</h2>
                  <p className="mt-1 text-sm text-ink-muted">{course.description}</p>
                  <p className="mt-2 font-mono text-xs text-ink-muted">
                    ~{course.estimated_minutes} min
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded border px-2 py-0.5 font-mono text-[11px] ${
                    course.completed
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border text-ink-muted"
                  }`}
                >
                  {course.completed ? "concluído" : "pendente"}
                </span>
              </div>

              <div className="mt-3">
                {course.lab_id && (
                  <Link
                    href={`/labs/${course.lab_id}`}
                    className="rounded border border-trace/40 bg-trace/10 px-3 py-1.5 text-xs text-trace hover:bg-trace/20"
                  >
                    Ir para o lab
                  </Link>
                )}
                {course.has_quiz && (
                  <QuizBlock course={course} onCompleted={reload} />
                )}
                {!course.lab_id && !course.has_quiz && !course.completed && (
                  <button
                    onClick={() => handleCompleteTheory(course.id)}
                    className="rounded border border-border px-3 py-1.5 text-xs text-ink-muted hover:border-trace/60 hover:text-trace"
                  >
                    Marcar como concluído
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
