export type Priority = "low" | "medium" | "high" | "urgent";
export type TaskStatus = "todo" | "in_progress" | "done";
export type EventKind = "meeting" | "focus" | "study" | "personal" | "break";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: Priority;
  due_at: string | null;
  estimate_minutes: number;
  tags: string[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface EventItem {
  id: string;
  title: string;
  description: string;
  start_at: string;
  end_at: string;
  location: string;
  kind: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface Reminder {
  id: string;
  title: string;
  note: string;
  remind_at: string;
  status: "pending" | "dismissed";
  created_at: string;
  updated_at: string;
}

export interface ActivityEntry {
  id: string;
  workflow_id: string | null;
  action_id: string | null;
  provider_type: string;
  provider_name: string;
  operation: string;
  status: "success" | "failed" | "rejected";
  message: string;
  simulated: boolean;
  detail: Record<string, unknown>;
  created_at: string;
}

export type ActionStatus =
  | "proposed"
  | "approved"
  | "rejected"
  | "executing"
  | "executed"
  | "failed";

export type WorkflowStatus =
  | "pending_approval"
  | "executing"
  | "completed"
  | "partial"
  | "rejected"
  | "failed";

export interface WorkflowAction {
  id: string;
  workflow_id: string;
  order_index: number;
  action_type: string;
  provider: string;
  title: string;
  description: string;
  payload: Record<string, any>;
  preview: {
    change?: string;
    entity?: string;
    summary?: string;
    before?: unknown;
    after?: any;
    reason?: string;
    conflicts?: PlanConflict[];
    [key: string]: unknown;
  };
  status: ActionStatus;
  result: Record<string, any>;
  error: string;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
  executed_at: string | null;
}

export interface WorkflowStep {
  id: string;
  title: string;
  detail: string;
  status: string;
  provider: string | null;
}

export interface PlanConflict {
  severity: "info" | "warning" | "critical" | string;
  title: string;
  detail: string;
  related_ids?: string[];
}

export interface PlanBlock {
  start_at: string;
  end_at: string;
  display: string;
  title: string;
  type: "event" | "task" | "study";
  kind: string;
  reason: string;
  task_id: string | null;
  event_id: string | null;
  priority: Priority | null;
  duration_minutes: number;
}

export interface PlanGap {
  start_at: string;
  end_at: string;
  display: string;
  duration_minutes: number;
}

export interface DayPlan {
  date: string;
  window: { start_at: string; end_at: string; label: string };
  blocks: PlanBlock[];
  conflicts: PlanConflict[];
  rationale: string[];
  unscheduled_tasks: Array<Pick<Task, "id" | "title" | "priority" | "estimate_minutes">>;
  stats: {
    busy_minutes: number;
    scheduled_focus_minutes: number;
    free_minutes: number;
    tasks_considered: number;
    tasks_scheduled: number;
    tasks_unscheduled: number;
    events: number;
  };
  gaps: PlanGap[];
}

export interface Workflow {
  id: string;
  command: string;
  intent: string;
  intent_label: string;
  summary: string;
  plan: {
    steps?: WorkflowStep[];
    rationale?: string[];
    conflicts?: PlanConflict[];
    preview?: { plan?: DayPlan; command?: string; [key: string]: unknown };
    skipped_duplicates?: Array<{ title: string; reason: string }>;
    ai?: {
      mode: string;
      label: string;
      llm_used: boolean;
      explanation: string;
      matched_rule: string;
      confidence: number;
    };
    providers?: ProviderInfo[];
  };
  result: {
    executed?: number;
    failed?: number;
    failures?: string[];
    status?: string;
    tasks?: Task[];
    count?: number;
    [key: string]: unknown;
  };
  status: WorkflowStatus;
  provider_mode: string;
  ai_mode: string;
  target_date: string | null;
  created_at: string;
  updated_at: string;
  decided_at: string | null;
  executed_at: string | null;
  error: string | null;
  actions: WorkflowAction[];
}

export interface DashboardData {
  date: string;
  settings: { display_name: string; time_format: "12h" | "24h"; day_start: string; day_end: string };
  events_today: EventItem[];
  next_event: EventItem | null;
  upcoming_events: EventItem[];
  pending_tasks: Task[];
  completed_today: Task[];
  reminders: Reminder[];
  recent_activity: ActivityEntry[];
  stats: {
    pending_count: number;
    completed_today: number;
    completion_rate: number;
    overdue_count: number;
    urgent_count: number;
    focus_minutes_today: number;
    scheduled_minutes_today: number;
    free_minutes_today: number;
    weekly_completions: Array<{ date: string; label: string; count: number }>;
  };
  pending_approvals: number;
}

export interface ProviderInfo {
  key: string;
  label: string;
  kind: "local" | "mcp";
  transport: string;
  status: "connected" | "not_configured" | "error";
  note: string;
}

export interface SystemStatus {
  app: string;
  version: string;
  demo_mode: boolean;
  demo_label: string;
  provider_mode: string;
  providers: ProviderInfo[];
  ai: {
    mode: string;
    label: string;
    description: string;
    llm_configured: boolean;
    requires_api_key: boolean;
    requested: string;
    fallback_active: boolean;
    supported_intents: Array<{ intent: string; example: string }>;
  };
  storage: { engine: string; persistent: boolean; note: string };
  integrations: Array<{ name: string; status: string; detail: string }>;
}

export interface Settings {
  display_name: string;
  role: string;
  workspace: string;
  time_format: "12h" | "24h";
  week_start: "monday" | "sunday";
  day_start: string;
  day_end: string;
  focus_block_minutes: number;
  default_study_minutes: number;
  buffer_minutes: number;
  min_block_minutes: number;
}

export interface PlannerResponse {
  plan: DayPlan;
  pending_tasks: Task[];
  window: { start: string; end: string; buffer_minutes: number };
}

export interface ActivityResponse {
  entries: ActivityEntry[];
  summary: {
    total: number;
    counts: { success: number; failed: number; rejected: number };
    providers: Array<{ provider_type: string; count: number }>;
  };
}
