/**
 * Cliente de API do Core API.
 *
 * Decisão: o JWT é guardado em localStorage no MVP para simplicidade.
 * Isso é aceitável porque o token tem vida curta (15 min, ver
 * core-api/app/config.py) e a superfície de XSS deve ser mitigada por
 * CSP + sanitização de saída. Antes da Fase 5 (produção real), avaliar
 * migrar para cookie httpOnly + refresh token rotativo, que reduz a
 * exposição a roubo de token via XSS.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UserOut = {
  id: string;
  email: string;
  role: "student" | "instructor" | "org_admin" | "super_admin";
  xp: number;
  level: number;
  organization_id: string;
};

export type LabOut = {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  difficulty: string;
  estimated_minutes: number;
  status: string;
};

export type LabSessionOut = {
  id: string;
  lab_id: string;
  status: string;
  started_at: string;
  expires_at: string | null;
  access_url?: string | null;
};

export type SubmissionOut = {
  id: string;
  correct: boolean;
  points_awarded: number;
  submitted_at: string;
};

export type CourseOut = {
  id: string;
  title: string;
  slug: string;
  description: string;
  order_index: number;
  estimated_minutes: number;
  lab_id: string | null;
  has_quiz: boolean;
  completed: boolean;
};

export type LearningPathOut = {
  id: string;
  title: string;
  slug: string;
  description: string;
  status: string;
};

export type LearningPathDetailOut = LearningPathOut & {
  courses: CourseOut[];
  progress_completed: number;
  progress_total: number;
  progress_percent: number;
};

export type QuizQuestionOut = {
  id: string;
  prompt: string;
  options: string[];
};

export type QuizResultOut = {
  score_percent: number;
  passed: boolean;
  course_completed: boolean;
};

export type BadgeOut = {
  slug: string;
  name: string;
  description: string;
};

export type AchievementOut = {
  badge: BadgeOut;
  earned_at: string;
};

export type LoginResult = {
  access_token: string | null;
  mfa_required: boolean;
  mfa_pending_token: string | null;
};

export type TeamOut = {
  id: string;
  organization_id: string;
  name: string;
};

export type TeamDetailOut = TeamOut & {
  members: UserOut[];
};

export type ReportOut = {
  id: string;
  title: string;
  generated_at: string;
  content: {
    executive_summary: string;
    scope: string;
    methodology: string;
    findings: Array<{
      title: string;
      category: string;
      severity: string;
      points: number;
      evidence: string;
      remediation: string;
    }>;
    conclusion: string;
  };
};

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("vr_token");
}

export function setToken(token: string) {
  window.localStorage.setItem("vr_token", token);
}

export function clearToken() {
  window.localStorage.removeItem("vr_token");
}

async function request<T>(
  path: string,
  options: RequestInit & { form?: Record<string, string> } = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  let body = options.body;
  if (options.form) {
    body = new URLSearchParams(options.form).toString();
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body && !(body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
  }

  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers, body });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* corpo não era JSON */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  async register(email: string, password: string) {
    return request<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  async login(email: string, password: string) {
    return request<LoginResult>("/auth/login", {
      method: "POST",
      form: { username: email, password },
    });
  },
  async mfaLoginVerify(mfaPendingToken: string, code: string) {
    return request<LoginResult>("/auth/mfa/login-verify", {
      method: "POST",
      body: JSON.stringify({ mfa_pending_token: mfaPendingToken, code }),
    });
  },
  async mfaSetup() {
    return request<{ provisioning_uri: string; secret: string }>("/auth/mfa/setup", {
      method: "POST",
    });
  },
  async mfaVerify(code: string) {
    return request<{ access_token: string }>("/auth/mfa/verify", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
  },
  async me() {
    return request<UserOut>("/users/me");
  },
  async listLabs() {
    return request<LabOut[]>("/labs");
  },
  async getLab(id: string) {
    return request<LabOut>(`/labs/${id}`);
  },
  async startLabSession(labId: string) {
    return request<LabSessionOut>("/lab-sessions", {
      method: "POST",
      body: JSON.stringify({ lab_id: labId }),
    });
  },
  async terminateLabSession(instanceId: string) {
    return request<LabSessionOut>(`/lab-sessions/${instanceId}/terminate`, {
      method: "POST",
    });
  },
  async submitFlag(labInstanceId: string, flagValue: string) {
    return request<SubmissionOut>("/submissions", {
      method: "POST",
      body: JSON.stringify({ lab_instance_id: labInstanceId, flag_value: flagValue }),
    });
  },
  async listLearningPaths() {
    return request<LearningPathOut[]>("/learning-paths");
  },
  async getLearningPath(id: string) {
    return request<LearningPathDetailOut>(`/learning-paths/${id}`);
  },
  async getCourseQuiz(courseId: string) {
    return request<QuizQuestionOut[]>(`/courses/${courseId}/quiz`);
  },
  async submitQuiz(courseId: string, answers: Record<string, number>) {
    return request<QuizResultOut>(`/courses/${courseId}/quiz/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });
  },
  async completeTheoryCourse(courseId: string) {
    return request<CourseOut>(`/courses/${courseId}/complete`, { method: "POST" });
  },
  async myAchievements() {
    return request<AchievementOut[]>("/users/me/achievements");
  },
  async listTeams() {
    return request<TeamOut[]>("/teams");
  },
  async getTeam(id: string) {
    return request<TeamDetailOut>(`/teams/${id}`);
  },
  async generateReport(title: string) {
    return request<ReportOut>("/reports/generate", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },
  async listMyReports() {
    return request<ReportOut[]>("/reports");
  },
  async getReport(id: string) {
    return request<ReportOut>(`/reports/${id}`);
  },
};

export { ApiError };
