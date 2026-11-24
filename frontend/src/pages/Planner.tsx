import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CalendarClock,
  ChevronRight,
  CircleDot,
  Clock,
  Route,
  Send,
  Sunrise,
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
  PageHeader,
  PriorityBadge,
  StatTile,
  TextInput,
} from "../components/ui";
import { durationLabel, fmtDate, fmtTime, todayISO } from "../lib/format";
import type { PlanConflict } from "../lib/types";

const conflictStyles: Record<string, string> = {
  critical: "border-clay/35 bg-clay/[0.06]",
  warning: "border-brass/30 bg-brass/[0.05]",
  info: "border-sky/25 bg-sky/[0.04]",
};

const conflictIcon: Record<string, string> = {
  critical: "text-clay",
  warning: "text-brass",
  info: "text-sky",
};

function ConflictRow({ conflict }: { conflict: PlanConflict }) {
  return (
    <div className={cn("rounded-md border px-3 py-2", conflictStyles[conflict.severity] ?? conflictStyles.info)}>
      <div className="flex items-center gap-2">
        <AlertTriangle className={cn("size-3.5", conflictIcon[conflict.severity] ?? conflictIcon.info)} />
        <p className="text-[11.5px] font-semibold uppercase tracking-wide text-bone-dim">{conflict.title}</p>
        <Badge tone={conflict.severity === "critical" ? "clay" : conflict.severity === "warning" ? "brass" : "sky"}>
          {conflict.severity}
        </Badge>
      </div>
      <p className="mt-1 text-[12px] leading-relaxed text-muted">{conflict.detail}</p>
    </div>
  );
}

export default function PlannerPage() {
  const [date, setDate] = useState(todayISO());
  const [proposing, setProposing] = useState(false);
  const { settings } = useSettings();
  const toast = useToast();
  const navigate = useNavigate();
  const planner = useApi(() => api.plannerDay(date), [date]);
  const format = settings.time_format;

  const plan = planner.data?.plan;

  const propose = async () => {
    setProposing(true);
    try {
      await api.proposePlan(date);
      toast("Schedule sent to the Approval Center. Nothing is written yet.");
      navigate("/approvals");
    } catch (cause) {
      toast(cause instanceof Error ? cause.message : "Could not propose the plan.", "error");
    } finally {
      setProposing(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Daily Planner"
        title="A schedule that explains itself."
        description="Calendar events and pending tasks are combined into a conflict-aware day plan. Every block states why it earned its slot."
        actions={
          <>
            <div className="flex items-center gap-2 rounded-md border border-line bg-ink-900 px-2.5 py-1.5">
              <CalendarClock className="size-4 text-muted" />
              <TextInput
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value || todayISO())}
                aria-label="Plan date"
                className="h-6 border-0 bg-transparent px-1 py-0 text-[12.5px] focus:shadow-none"
              />
            </div>
            <Button
              variant="primary"
              icon={<Send className="size-4" />}
              loading={proposing}
              disabled={!plan || plan.blocks.length === 0}
              onClick={propose}
            >
              Propose for approval
            </Button>
          </>
        }
      />

      {planner.error && <ErrorPanel message={planner.error} onRetry={planner.reload} />}

      {planner.loading && !planner.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="panel h-[92px] animate-pulse" />
            ))}
          </div>
          <Card>
            <div className="space-y-2 p-5">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-11 animate-pulse rounded bg-ink-850" />
              ))}
            </div>
          </Card>
        </div>
      )}

      {plan && (
        <div className="animate-enter space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Scheduled focus"
              value={durationLabel(plan.stats.scheduled_focus_minutes)}
              hint={`${plan.stats.tasks_scheduled} task block(s)`}
              accent="brass"
            />
            <StatTile
              label="Open time left"
              value={durationLabel(plan.stats.free_minutes)}
              hint={plan.window.label}
              accent="sage"
            />
            <StatTile
              label="Calendar events"
              value={plan.stats.events}
              hint={`${durationLabel(plan.stats.busy_minutes)} already booked`}
              accent="sky"
            />
            <StatTile
              label="Conflicts"
              value={plan.conflicts.length}
              hint={plan.stats.tasks_unscheduled ? `${plan.stats.tasks_unscheduled} task(s) unscheduled` : "All fit"}
              accent={plan.conflicts.length ? "clay" : "bone"}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
            <div className="space-y-4">
              <Card>
                <CardHeader
                  eyebrow={`${fmtDate(date, { weekday: "long", day: "numeric", month: "long" })} · ${plan.window.label}`}
                  title="Proposed timeline"
                  action={
                    <span className="text-[11px] text-muted">{settings.buffer_minutes} min buffers</span>
                  }
                />
                {plan.blocks.length === 0 ? (
                  <EmptyState icon={<Sunrise className="size-4" />} title="Nothing to place" description="There are no events or pending tasks for this date." />
                ) : (
                  <ol className="px-5 py-2">
                    {plan.blocks.map((block, index) => (
                      <li key={`${block.start_at}-${index}`} className="flex gap-3 py-2.5">
                        <div className="num w-[86px] shrink-0 pt-0.5 font-mono text-[11px] leading-tight text-muted">
                          <div className="text-bone-dim">{fmtTime(block.start_at, format)}</div>
                          <div className="text-[10px] text-muted/70">{fmtTime(block.end_at, format)}</div>
                        </div>
                        <div className="relative flex w-3 shrink-0 justify-center">
                          <span
                            className={cn(
                              "mt-1 size-2 rounded-full ring-4 ring-ink-900",
                              block.type === "event"
                                ? "bg-sky"
                                : block.type === "study"
                                  ? "bg-brass"
                                  : "bg-sage",
                            )}
                          />
                          {index < plan.blocks.length - 1 && (
                            <span className="absolute top-4 h-[calc(100%-4px)] w-px bg-line" aria-hidden />
                          )}
                        </div>
                        <div className="min-w-0 flex-1 pb-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-[13px] font-medium text-bone">{block.title}</p>
                            <Badge tone={block.type === "event" ? "neutral" : block.type === "study" ? "brass" : "sage"}>
                              {block.type === "event" ? block.kind : block.type}
                            </Badge>
                            <span className="text-[10.5px] text-muted">{durationLabel(block.duration_minutes)}</span>
                            {block.priority && <PriorityBadge priority={block.priority} />}
                          </div>
                          <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{block.reason}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </Card>

              <Card>
                <CardHeader eyebrow="Open space" title="Remaining gaps" />
                {plan.gaps.length === 0 ? (
                  <EmptyState icon={<Clock className="size-4" />} title="Fully booked" description="No remaining gaps inside the working window." />
                ) : (
                  <div className="divide-y divide-line-soft">
                    {plan.gaps.map((gap) => (
                      <div key={gap.start_at} className="flex items-center gap-3 px-5 py-2.5">
                        <CircleDot className="size-3.5 text-muted/60" />
                        <span className="num font-mono text-[11.5px] text-bone-dim">{gap.display}</span>
                        <span className="text-[11px] text-muted">{durationLabel(gap.duration_minutes)} available</span>
                        <span className="ml-auto text-[10.5px] text-muted/70">unscheduled</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardHeader eyebrow="Checks" title="Conflicts & risks" />
                <div className="space-y-2 p-4">
                  {plan.conflicts.length === 0 ? (
                    <div className="rounded-md border border-sage/25 bg-sage/[0.04] px-3 py-2.5">
                      <p className="text-[12px] text-bone-dim">No conflicts detected.</p>
                      <p className="mt-0.5 text-[11px] text-muted">The proposed blocks respect existing events and buffers.</p>
                    </div>
                  ) : (
                    plan.conflicts.map((conflict, index) => <ConflictRow key={index} conflict={conflict} />)
                  )}
                </div>
              </Card>

              <Card>
                <CardHeader eyebrow="Explainability" title="Prioritisation decisions" />
                <ul className="space-y-2 px-5 py-4">
                  {plan.rationale.map((reason, index) => (
                    <li key={index} className="flex gap-2 text-[11.5px] leading-relaxed text-muted">
                      <ChevronRight className="mt-0.5 size-3 shrink-0 text-brass/70" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </Card>

              {plan.unscheduled_tasks.length > 0 && (
                <Card>
                  <CardHeader eyebrow="Overflow" title="Not scheduled" />
                  <div className="divide-y divide-line-soft">
                    {plan.unscheduled_tasks.map((task) => (
                      <div key={task.id} className="flex items-center gap-2 px-5 py-2.5">
                        <span className="min-w-0 flex-1 truncate text-[12px] text-bone-dim">{task.title}</span>
                        <PriorityBadge priority={task.priority} />
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              <Card className="px-5 py-4">
                <div className="flex items-center gap-2">
                  <Route className="size-4 text-brass" />
                  <span className="label-micro text-bone-dim">How to use this plan</span>
                </div>
                <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
                  The planner is read-only. “Propose for approval” turns these blocks into pending
                  calendar actions; they appear in the Approval Center and are only written after you
                  approve and execute them.
                </p>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
