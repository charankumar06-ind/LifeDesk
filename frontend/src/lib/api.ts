import type {
  ActivityResponse,
  DashboardData,
  DayPlan,
  EventItem,
  PlannerResponse,
  Reminder,
  Settings,
  SystemStatus,
  Task,
  Workflow,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Cannot reach the LifeDesk backend. Is the FastAPI server running on port 8000?",
      0,
    );
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
      else if (Array.isArray(body?.detail)) {
        message = body.detail
          .map((item: { msg?: string; loc?: string[] }) => item.msg ?? "Invalid value")
          .join(" · ");
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  dashboard: () => request<DashboardData>("/dashboard"),

  tasks: (params: { status?: string; priority?: string; search?: string } = {}) =>
    request<{ tasks: Task[] }>(`/tasks${query(params)}`),
  createTask: (payload: Partial<Task>) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (id: string, payload: Partial<Task>) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTask: (id: string) => request<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" }),

  events: (start: string, end: string) =>
    request<{ events: EventItem[] }>(`/events${query({ start, end })}`),
  createEvent: (payload: Partial<EventItem>) =>
    request<EventItem>("/events", { method: "POST", body: JSON.stringify(payload) }),
  updateEvent: (id: string, payload: Partial<EventItem>) =>
    request<EventItem>(`/events/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteEvent: (id: string) => request<{ ok: boolean }>(`/events/${id}`, { method: "DELETE" }),

  reminders: (status?: string) =>
    request<{ reminders: Reminder[] }>(`/reminders${query({ status })}`),
  dismissReminder: (id: string) =>
    request<Reminder>(`/reminders/${id}/dismiss`, { method: "POST" }),

  plannerDay: (date: string) => request<PlannerResponse>(`/planner/day${query({ date })}`),
  proposePlan: (date: string) =>
    request<Workflow>("/planner/propose", { method: "POST", body: JSON.stringify({ date }) }),

  runCommand: (command: string) =>
    request<Workflow>("/commands", { method: "POST", body: JSON.stringify({ command }) }),
  workflows: (params: { status?: string; limit?: number } = {}) =>
    request<{ workflows: Workflow[] }>(`/workflows${query(params)}`),

  approvals: () =>
    request<{ pending: Workflow[]; recent: Workflow[] }>("/approvals"),
  decideAction: (workflowId: string, actionId: string, decision: "approve" | "reject") =>
    request<Workflow>(`/approvals/${workflowId}/actions/${actionId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  decideAll: (workflowId: string, decision: "approve" | "reject") =>
    request<Workflow>(`/approvals/${workflowId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  executeWorkflow: (workflowId: string) =>
    request<Workflow>(`/approvals/${workflowId}/execute`, { method: "POST" }),

  activity: (params: { limit?: number; status?: string; provider?: string } = {}) =>
    request<ActivityResponse>(`/activity${query(params)}`),

  settings: () => request<Settings>("/settings"),
  saveSettings: (payload: Settings) =>
    request<Settings>("/settings", { method: "PUT", body: JSON.stringify(payload) }),
  system: () => request<SystemStatus>("/system"),
};

export type { DayPlan };
