import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Bell,
  CalendarDays,
  Check,
  CircleCheckBig,
  Clock,
  Command,
  ListChecks,
  MapPin,
  ShieldCheck,
  Timer,
  TrendingUp,
} from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { useSettings } from "../components/SettingsProvider";
import { useToast } from "../components/Toast";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  MiniAreaChart,
  PageHeader,
  PriorityBadge,
  SimulationChip,
  StatTile,
  StatusBadge,
} from "../components/ui";
import {
  durationLabel,
  fmtDate,
  fmtDateTime,
  fmtTime,
  relativeTime,
  todayISO,
} from "../lib/format";
import type { EventItem, Task } from "../lib/types";

const kindAccent: Record<string, string> = {
  meeting: "bg-sky",
  focus: "bg-brass",
  study: "bg-brass",
  personal: "bg-sage",
  break: "bg-muted",
};

function greeting(hour: number) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

type FlowStage = {
  key: string;
  label: string;
  value: number;
  caption: string;
  note: string;
  tone: string;
};

function eventMinutes(events: EventItem[], kind: string): number {
  return events
    .filter((event) => event.kind === kind)
    .reduce(
      (sum, event) =>
        sum +
        Math.max(0, Math.round((new Date(event.end_at).getTime() - new Date(event.start_at).getTime()) / 60000)),
      0,
    );
}

function StageFlow({
  events,
  pendingTasks,
  pendingApprovals,
  completedToday,
  activityCount,
  focusMinutes,
  scheduledMinutes,
  freeMinutes,
}: {
  events: EventItem[];
  pendingTasks: number;
  pendingApprovals: number;
  completedToday: number;
  activityCount: number;
  focusMinutes: number;
  scheduledMinutes: number;
  freeMinutes: number;
}) {
  const stages: FlowStage[] = [
    { key: "intake", label: "Intake", value: events.length, caption: "events today", note: "What arrives", tone: "#38bdf8" },
    { key: "plan", label: "Plan", value: pendingTasks, caption: "open tasks", note: "What is queued", tone: "#9d8bff" },
    { key: "approve", label: "Approve", value: pendingApprovals, caption: "awaiting you", note: "Your call", tone: "#e0b25c" },
    { key: "execute", label: "Execute", value: completedToday, caption: "done today", note: "Provider writes", tone: "#4fd6a8" },
    { key: "log", label: "Log", value: activityCount, caption: "entries", note: "Audit trail", tone: "#a9a5c9" },
  ];

  const total = scheduledMinutes + freeMinutes;
  const meetingMinutes = eventMinutes(events, "meeting");
  const otherMinutes = Math.max(0, scheduledMinutes - focusMinutes - meetingMinutes);
  const rawSegments = [
    { label: "Focus", minutes: focusMinutes, tone: "#9d8bff" },
    { label: "Meetings", minutes: meetingMinutes, tone: "#38bdf8" },
    ...(otherMinutes > 0 ? [{ label: "Other", minutes: otherMinutes, tone: "#a9a5c9" }] : []),
    { label: "Open", minutes: Math.max(0, freeMinutes), tone: "#4fd6a8" },
  ];
  let assigned = 0;
  const segments = rawSegments.map((segment, index) => {
    const pct =
      index === rawSegments.length - 1
        ? Math.max(0, 100 - assigned)
        : Math.round(total > 0 ? (segment.minutes / total) * 100 : 0);
    assigned += pct;
    return { ...segment, pct };
  });

  return (
    <div>
      <div className="overflow-x-auto">
        <div className="flex min-w-[820px] items-stretch gap-1.5 px-5 py-5">
          {stages.map((stage, index) => {
            const active = stage.key === "approve" && pendingApprovals > 0;
            return (
              <Fragment key={stage.key}>
                <div
                  className={cn(
                    "relative flex-1 overflow-hidden rounded-xl border px-3.5 py-3",
                    active
                      ? "border-brass/40 bg-brass/[0.07]"
                      : "border-white/[0.07] bg-white/[0.02]",
                  )}
                >
                  <span
                    className="absolute inset-x-3 top-0 h-px"
                    style={{ background: `linear-gradient(90deg, transparent, ${stage.tone}, transparent)` }}
                    aria-hidden
                  />
                  <div className="flex items-center justify-between gap-2">
                    <span className="label-micro">{stage.label}</span>
                    <span className="num font-mono text-[10px] text-muted/60">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <div className="num mt-2.5 text-[28px] font-semibold leading-none" style={{ color: stage.tone }}>
                    {stage.value}
                  </div>
                  <div className="mt-1.5 text-[10.5px] text-muted">{stage.caption}</div>
                  <div className="mt-2 text-[9.5px] uppercase tracking-wide text-muted/60">{stage.note}</div>
                </div>
                {index < stages.length - 1 && (
                  <ArrowRight className="size-4 shrink-0 self-center text-white/20" aria-hidden />
                )}
              </Fragment>
            );
          })}
        </div>
      </div>

      <div className="border-t border-white/[0.06] px-5 py-3">
        <div className="flex h-1.5 overflow-hidden rounded-full bg-white/[0.06]" aria-hidden>
          {segments.map((segment) =>
            segment.pct > 0 ? (
              <div
                key={segment.label}
                className="h-full"
                style={{ width: `${segment.pct}%`, backgroundColor: segment.tone }}
              />
            ) : null,
          )}
        </div>
        <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-2">
          {segments.map((segment) => (
            <span key={segment.label} className="inline-flex items-center gap-2 text-[11.5px] text-muted">
              <span className="size-1.5 rounded-full" style={{ backgroundColor: segment.tone }} aria-hidden />
              {segment.label}
              <span className="num font-semibold text-bone-dim">{segment.pct}%</span>
              <span className="num text-[10.5px] text-muted/70">{durationLabel(segment.minutes)}</span>
            </span>
          ))}
          <span className="ml-auto text-[10.5px] text-muted/80">
            Share of today's working window · {durationLabel(Math.max(0, total))}
          </span>
        </div>
      </div>
    </div>
  );
}

function ScheduleRow({ event, format }: { event: EventItem; format: "12h" | "24h" }) {
  return (
    <div className="flex gap-3 px-5 py-3">
      <div className="num w-[86px] shrink-0 pt-0.5 font-mono text-[11.5px] leading-tight text-muted">
        <div className="text-bone-dim">{fmtTime(event.start_at, format)}</div>
        <div className="text-[10.5px] text-muted/70">{fmtTime(event.end_at, format)}</div>
      </div>
      <div className={cn("w-px self-stretch rounded", kindAccent[event.kind] ?? "bg-muted", "opacity-70")} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-bone">{event.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
          <span className="capitalize">{event.kind}</span>
          {event.location && (
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3" /> {event.location}
            </span>
          )}
          <span>{durationLabel(Math.round((new Date(event.end_at).getTime() - new Date(event.start_at).getTime()) / 60000))}</span>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data, loading, error, reload } = useApi(() => api.dashboard(), []);
  const systemApi = useApi(() => api.system(), []);
  const system = systemApi.data;
  const providerMode = system?.provider_mode ?? "local";
  const mcpDegraded = providerMode === "mcp" && system?.mcp?.status === "error";
  const { settings } = useSettings();
  const toast = useToast();
  const [busyTask, setBusyTask] = useState<string | null>(null);

  const format = settings.time_format;
  const today = todayISO();
  const profileFirst = settings.display_name.trim().split(/\s+/)[0] ?? "";
  const pendingApprovals = data?.pending_approvals ?? 0;
  const stats = data?.stats;

  const completeTask = async (task: Task) => {
    setBusyTask(task.id);
    try {
      await api.updateTask(task.id, { status: "done" });
      toast(`Marked “${task.title}” as done.`);
      reload();
    } catch (cause) {
      toast(cause instanceof Error ? cause.message : "Could not update the task.", "error");
    } finally {
      setBusyTask(null);
    }
  };

  const dismissReminder = async (id: string) => {
    try {
      await api.dismissReminder(id);
      toast("Reminder dismissed.");
      reload();
    } catch (cause) {
      toast(cause instanceof Error ? cause.message : "Could not dismiss the reminder.", "error");
    }
  };

  const weekly = stats?.weekly_completions ?? [];

  return (
    <div>
      <PageHeader
        eyebrow={fmtDate(today, { weekday: "long", day: "numeric", month: "long" })}
        title={`${greeting(new Date().getHours())}${profileFirst ? `, ${profileFirst}.` : "."}`}
        description="Your day at a glance — schedule, pending work, and what the workflow engine has been doing."
        actions={
          <>
            <Link to="/tasks">
              <Button variant="secondary" icon={<ListChecks className="size-4" />}>
                Tasks
              </Button>
            </Link>
            <Link to="/command">
              <Button variant="primary" icon={<Command className="size-4" />}>
                Command center
              </Button>
            </Link>
          </>
        }
      />

      {pendingApprovals > 0 && (
        <Link
          to="/approvals"
          className="animate-enter mb-5 flex flex-wrap items-center gap-3 rounded-2xl border border-brass/25 bg-[linear-gradient(120deg,rgba(124,92,255,0.18),rgba(255,255,255,0.02))] px-4 py-3 transition-colors hover:border-brass/45"
        >
          <ShieldCheck className="size-4 text-brass" />
          <p className="text-[12.5px] text-bone-dim">
            <span className="font-semibold text-brass">{pendingApprovals}</span> workflow
            {pendingApprovals === 1 ? "" : "s"} awaiting your approval. Nothing is executed automatically.
          </p>
          <span className="ml-auto inline-flex items-center gap-1 text-[12px] text-brass">
            Review <ArrowUpRight className="size-3.5" />
          </span>
        </Link>
      )}

      {error && <ErrorPanel message={error} onRetry={reload} />}

      {loading && !data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="panel h-[92px] animate-pulse" />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
            <Card>
              <LoadingBlock rows={4} />
            </Card>
            <Card>
              <LoadingBlock rows={3} />
            </Card>
          </div>
        </div>
      )}

      {data && stats && (
        <div className="animate-enter space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Pending tasks"
              value={stats.pending_count}
              hint={`${stats.urgent_count} high or urgent`}
              accent="brass"
              icon={<ListChecks className="size-4" />}
            />
            <StatTile
              label="Completed today"
              value={stats.completed_today}
              hint={`${stats.completion_rate}% lifetime completion`}
              accent="sage"
              icon={<CircleCheckBig className="size-4" />}
            />
            <StatTile
              label="Focus time today"
              value={durationLabel(stats.focus_minutes_today)}
              hint={`${durationLabel(stats.scheduled_minutes_today)} scheduled in total`}
              accent="sky"
              icon={<Timer className="size-4" />}
            />
            <div className="panel relative overflow-hidden px-4 py-4">
              <div className="flex items-start justify-between gap-2">
                <span className="label-micro pt-1">7-day output</span>
                <span className="icon-chip shrink-0 border-brass/30 bg-brass/[0.16] text-[#bdb0ff] shadow-[0_0_22px_-6px_rgba(139,124,255,0.7)]">
                  <TrendingUp className="size-4" />
                </span>
              </div>
              <div className="num mt-2.5 text-[28px] font-semibold leading-none tracking-[-0.02em]">
                {weekly.reduce((sum, entry) => sum + entry.count, 0)}
              </div>
              <div className="-mx-1 mt-1">
                <MiniAreaChart values={weekly.map((entry) => entry.count)} height={40} />
              </div>
              <div className="flex justify-between text-[9px] uppercase tracking-wide text-muted/70">
                {weekly.map((entry) => (
                  <span key={entry.date} className={entry.date === today ? "font-semibold text-brass" : undefined}>
                    {entry.label[0]}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <Card className="panel-glow overflow-hidden">
            <CardHeader
              eyebrow="Live routing"
              title="How today's work moves"
              action={
                <Badge tone="sage" dot>
                  Live
                </Badge>
              }
            />
            <StageFlow
              events={data.events_today}
              pendingTasks={stats.pending_count}
              pendingApprovals={pendingApprovals}
              completedToday={stats.completed_today}
              activityCount={data.recent_activity.length}
              focusMinutes={stats.focus_minutes_today}
              scheduledMinutes={stats.scheduled_minutes_today}
              freeMinutes={stats.free_minutes_today}
            />
          </Card>

          {stats.overdue_count > 0 && (
            <div className="flex items-center gap-2 rounded-md border border-clay/25 bg-clay/[0.05] px-3.5 py-2">
              <Clock className="size-3.5 text-clay" />
              <p className="text-[12px] text-bone-dim">
                {stats.overdue_count} task{stats.overdue_count === 1 ? " is" : "s are"} past the due time.
              </p>
              <Link to="/tasks" className="ml-auto text-[11.5px] text-clay hover:underline">
                Review
              </Link>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
            <div className="space-y-4">
              <Card>
                <CardHeader
                  eyebrow="Today"
                  title="Schedule"
                  action={
                    <Link to="/calendar" className="text-[12px] text-brass hover:underline">
                      Open calendar
                    </Link>
                  }
                />
                {data.events_today.length === 0 ? (
                  <EmptyState
                    icon={<CalendarDays className="size-4" />}
                    title="The day is open"
                    description="No events are booked yet. Ask the command center to plan your day."
                    action={
                      <Link to="/command">
                        <Button size="sm" variant="secondary">Plan my day</Button>
                      </Link>
                    }
                  />
                ) : (
                  <div className="divide-y divide-line-soft">
                    {data.events_today.map((event) => (
                      <ScheduleRow key={event.id} event={event} format={format} />
                    ))}
                  </div>
                )}
                {data.next_event && (
                  <div className="flex flex-wrap items-center gap-2 border-t border-line-soft bg-ink-850/50 px-5 py-2.5">
                    <span className="label-micro">Next up</span>
                    <span className="text-[12px] text-bone-dim">
                      {data.next_event.title} · {fmtTime(data.next_event.start_at, format)}
                    </span>
                    {data.next_event.location && (
                      <span className="ml-auto text-[11px] text-muted">{data.next_event.location}</span>
                    )}
                  </div>
                )}
              </Card>

              <Card>
                <CardHeader
                  eyebrow={`${stats.pending_count} open`}
                  title="Pending tasks"
                  action={
                    <Link to="/tasks" className="text-[12px] text-brass hover:underline">
                      All tasks
                    </Link>
                  }
                />
                {data.pending_tasks.length === 0 ? (
                  <EmptyState
                    icon={<Check className="size-4" />}
                    title="Nothing pending"
                    description="Every task is complete. Add the next one when you are ready."
                  />
                ) : (
                  <div className="divide-y divide-line-soft">
                    {data.pending_tasks.slice(0, 6).map((task) => {
                      const overdue = task.due_at ? new Date(task.due_at) < new Date() : false;
                      return (
                        <div key={task.id} className="flex items-start gap-3 px-5 py-3">
                          <button
                            type="button"
                            aria-label={`Complete ${task.title}`}
                            disabled={busyTask === task.id}
                            onClick={() => completeTask(task)}
                            className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-[4px] border border-line text-transparent transition-colors hover:border-sage/60 hover:text-sage disabled:opacity-40"
                          >
                            {busyTask === task.id ? <span className="size-2 rounded-sm bg-muted" /> : <Check className="size-3" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-[12.5px] text-bone-dim">{task.title}</p>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-muted">
                              <PriorityBadge priority={task.priority} />
                              {task.due_at ? (
                                <span className={overdue ? "text-clay" : undefined}>
                                  {overdue ? "Overdue" : "Due"} {fmtDateTime(task.due_at, format)}
                                </span>
                              ) : (
                                <span>No deadline</span>
                              )}
                              <span>{durationLabel(task.estimate_minutes)}</span>
                              {task.tags.slice(0, 2).map((tag) => (
                                <span key={tag} className="rounded border border-line px-1.5 py-px text-[9.5px]">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardHeader eyebrow="Next 7 days" title="Upcoming events" />
                {data.upcoming_events.length === 0 ? (
                  <EmptyState title="Nothing on the horizon" description="The next week is clear." />
                ) : (
                  <div className="divide-y divide-line-soft">
                    {data.upcoming_events.map((event) => (
                      <div key={event.id} className="px-5 py-3">
                        <p className="text-[12.5px] text-bone-dim">{event.title}</p>
                        <p className="mt-0.5 text-[11px] text-muted">
                          {fmtDate(event.start_at, { weekday: "short", day: "numeric", month: "short" })} ·{" "}
                          {fmtTime(event.start_at, format)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card>
                <CardHeader
                  eyebrow="Reminders"
                  title="Don't forget"
                  action={
                    <Link to="/settings" className="text-[12px] text-muted hover:text-bone">
                      Settings
                    </Link>
                  }
                />
                {data.reminders.length === 0 ? (
                  <EmptyState icon={<Bell className="size-4" />} title="No reminders" description="Create one from the command center." />
                ) : (
                  <div className="divide-y divide-line-soft">
                    {data.reminders.map((reminder) => (
                      <div key={reminder.id} className="flex items-start gap-3 px-5 py-3">
                        <Bell className="mt-0.5 size-3.5 shrink-0 text-brass/80" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[12.5px] text-bone-dim">{reminder.title}</p>
                          <p className="mt-0.5 text-[10.5px] text-muted">
                            {fmtDateTime(reminder.remind_at, format)}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => dismissReminder(reminder.id)}
                          className="text-[10.5px] text-muted transition-colors hover:text-bone"
                        >
                          Dismiss
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card>
                <CardHeader
                  eyebrow="Activity"
                  title="Recent operations"
                  action={
                    <Link to="/activity" className="text-[12px] text-brass hover:underline">
                      Monitor
                    </Link>
                  }
                />
                {data.recent_activity.length === 0 ? (
                  <EmptyState title="No activity yet" description="Run a command to start the log." />
                ) : (
                  <div className="divide-y divide-line-soft">
                    {data.recent_activity.slice(0, 5).map((entry) => (
                      <div key={entry.id} className="px-5 py-2.5">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "size-1.5 shrink-0 rounded-full",
                              entry.status === "success"
                                ? "bg-sage"
                                : entry.status === "rejected"
                                  ? "bg-brass"
                                  : "bg-clay",
                            )}
                          />
                          <p className="min-w-0 flex-1 truncate text-[11.5px] text-bone-dim">
                            {entry.message}
                          </p>
                        </div>
                        <div className="mt-1 flex items-center gap-2 pl-3.5 text-[10px] text-muted">
                          <span className="font-mono">{entry.provider_name}</span>
                          <span>·</span>
                          <span>{relativeTime(entry.created_at)}</span>
                          {entry.simulated && <SimulationChip />}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card className="px-5 py-4">
                <div className="flex items-center justify-between">
                  <span className="label-micro">Provider mode</span>
                  <Badge tone={providerMode === "mcp" ? "sky" : providerMode === "local-fallback" ? "brass" : "sage"} dot>
                    {providerMode === "mcp" ? "MCP" : providerMode === "local-fallback" ? "Fallback" : "Local · SQLite"}
                  </Badge>
                </div>
                <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
                  {mcpDegraded
                    ? "The last MCP call failed, so this provider is degraded. Writes return 503 rather than falling back to local storage; the next successful call restores health."
                    : providerMode === "mcp"
                      ? `Calendar, task and reminder tools call the configured ${system?.mcp?.transport ?? "MCP"} MCP server. Approval still gates every write.`
                      : providerMode === "local-fallback"
                      ? "MCP was unavailable at startup, so SQLite providers are active. No workflow writes were routed to MCP."
                      : "Calendar, task and reminder tools are local providers behind the same interfaces MCP servers implement. Demo Mode — Local Data."}
                </p>
                <Link to="/settings" className="mt-2 inline-flex items-center gap-1 text-[11.5px] text-brass hover:underline">
                  Integration status <ArrowUpRight className="size-3" />
                </Link>
              </Card>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-muted">
            <StatusBadge status={mcpDegraded ? "error" : providerMode === "local-fallback" ? "fallback" : "connected"} />
            <span>{mcpDegraded ? "MCP providers degraded · no local fallback" : providerMode === "mcp" ? "MCP providers connected" : providerMode === "local-fallback" ? "Local fallback providers connected" : "Local providers connected"}</span>
            <span className="text-line">·</span>
            <span>{data.completed_today.length} task(s) completed today</span>
            <span className="text-line">·</span>
            <span>{stats.free_minutes_today > 0 ? `${durationLabel(stats.free_minutes_today)} unscheduled` : "Day is full"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
