import { useState, type ReactNode } from "react";
import {
  AlertTriangle,
  BellPlus,
  CalendarPlus,
  Check,
  CheckCheck,
  ChevronDown,
  Clock,
  Cpu,
  ListPlus,
  Mail,
  Minus,
  Play,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { fmtDateTime, fmtTime, relativeTime } from "../lib/format";
import { useSettings } from "./SettingsProvider";
import { Badge, Button, Card, PriorityBadge, SimulationChip, StatusBadge } from "./ui";
import { useToast } from "./Toast";
import type { Workflow, WorkflowStep } from "../lib/types";

const stepIcon = (status: string) => {
  switch (status) {
    case "done":
    case "completed":
      return <Check className="size-3" />;
    case "failed":
      return <X className="size-3" />;
    case "awaiting_approval":
      return <Clock className="size-3" />;
    case "skipped":
      return <Minus className="size-3" />;
    default:
      return <Check className="size-3" />;
  }
};

const stepTone: Record<string, string> = {
  done: "border-sage/40 bg-sage/10 text-sage",
  completed: "border-sage/40 bg-sage/10 text-sage",
  failed: "border-clay/40 bg-clay/10 text-clay",
  awaiting_approval: "border-brass/40 bg-brass/10 text-brass",
  skipped: "border-line bg-ink-800 text-muted",
};

function actionIcon(type: string) {
  if (type === "create_event") return <CalendarPlus className="size-4" />;
  if (type === "create_task") return <ListPlus className="size-4" />;
  if (type === "create_reminder") return <BellPlus className="size-4" />;
  if (type === "send_email") return <Mail className="size-4" />;
  return <Zap className="size-4" />;
}

function conflictTone(severity: string) {
  if (severity === "critical") return "border-clay/30 bg-clay/[0.06] text-clay";
  if (severity === "warning") return "border-brass/30 bg-brass/[0.05] text-brass";
  return "border-sky/25 bg-sky/[0.05] text-sky";
}

function Steps({ steps }: { steps: WorkflowStep[] }) {
  return (
    <ol className="space-y-0">
      {steps.map((step, index) => (
        <li key={`${step.id}-${index}`} className="flex gap-3 py-2.5 first:pt-0 last:pb-0">
          <span
            className={cn(
              "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
              stepTone[step.status] ?? "border-line bg-ink-800 text-muted",
            )}
          >
            {stepIcon(step.status)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <p className="text-[12.5px] font-medium text-bone-dim">{step.title}</p>
              {step.provider && (
                <span className="rounded border border-line bg-ink-850 px-1.5 py-px font-mono text-[10px] text-muted">
                  {step.provider}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted">{step.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function WorkflowView({
  workflow,
  interactive = false,
  collapsible = false,
  defaultOpen = true,
  onChanged,
  headerAction,
}: {
  workflow: Workflow;
  interactive?: boolean;
  collapsible?: boolean;
  defaultOpen?: boolean;
  onChanged?: (workflow: Workflow) => void;
  headerAction?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [busy, setBusy] = useState<string | null>(null);
  const toast = useToast();
  const { settings } = useSettings();
  const format = settings.time_format;

  const steps = workflow.plan.steps ?? [];
  const rationale = workflow.plan.rationale ?? [];
  const conflicts = workflow.plan.conflicts ?? [];
  const planPreview = workflow.plan.preview?.plan;
  const approvedCount = workflow.actions.filter((action) => action.status === "approved").length;
  const executedCount = workflow.actions.filter((action) => action.status === "executed").length;
  const pending = workflow.status === "pending_approval";

  const run = async (key: string, call: () => Promise<Workflow>, success: string) => {
    setBusy(key);
    try {
      const updated = await call();
      toast(success);
      onChanged?.(updated);
    } catch (error) {
      toast(error instanceof Error ? error.message : "The action could not be completed.", "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="animate-enter overflow-hidden">
      <div className="border-b border-line-soft px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="label-micro text-brass">{workflow.intent_label}</span>
            <StatusBadge status={workflow.status} />
            {workflow.actions.length > 0 && (
              <span className="text-[11px] text-muted">
                {workflow.actions.length} action{workflow.actions.length === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {headerAction}
            <span className="text-[11px] text-muted">{relativeTime(workflow.created_at)}</span>
            {collapsible && (
              <button
                type="button"
                aria-label={open ? "Collapse workflow" : "Expand workflow"}
                aria-expanded={open}
                onClick={() => setOpen((value) => !value)}
                className="rounded p-1 text-muted transition-colors hover:bg-ink-800 hover:text-bone"
              >
                <ChevronDown className={cn("size-4 transition-transform", !open && "-rotate-90")} />
              </button>
            )}
          </div>
        </div>

        <p className="serif mt-2.5 text-[18px] leading-snug text-bone">
          <span className="text-brass/70">“</span>
          {workflow.command}
          <span className="text-brass/70">”</span>
        </p>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{workflow.summary}</p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded border border-line bg-ink-850 px-2 py-0.5 text-[10.5px] text-muted">
            <Cpu className="size-3 text-brass/80" />
            {workflow.plan.ai?.llm_used ? "LLM interpretation" : "Deterministic interpreter · no LLM"}
          </span>
          {workflow.target_date && (
            <span className="text-[10.5px] text-muted">Target · {workflow.target_date}</span>
          )}
          <span className="font-mono text-[10.5px] text-muted/70">{workflow.id}</span>
        </div>
      </div>

      {open && (
        <div className="divide-y divide-line-soft">
          {workflow.error && (
            <div className="flex items-start gap-2.5 bg-clay/[0.05] px-5 py-3.5">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-clay" />
              <p className="text-[12px] leading-relaxed text-bone-dim">{workflow.error}</p>
            </div>
          )}

          {workflow.plan.skipped_duplicates && workflow.plan.skipped_duplicates.length > 0 && (
            <div className="px-5 py-4">
              <p className="label-micro mb-2">Duplicate actions blocked</p>
              {workflow.plan.skipped_duplicates.map((duplicate, index) => (
                <p key={index} className="text-[11.5px] leading-relaxed text-muted">
                  {duplicate.title} — {duplicate.reason}
                </p>
              ))}
            </div>
          )}

          <div className="px-5 py-4">
            <p className="label-micro mb-2.5 flex items-center gap-1.5">
              <Sparkles className="size-3 text-brass/70" /> Workflow plan
            </p>
            <Steps steps={steps} />
            {workflow.plan.ai?.explanation && (
              <p className="mt-3 border-l border-brass/30 pl-3 text-[11.5px] leading-relaxed text-muted">
                {workflow.plan.ai.explanation}
                {workflow.plan.ai.matched_rule && (
                  <span className="mt-1 block font-mono text-[10.5px] text-muted/70">
                    rule: {workflow.plan.ai.matched_rule}
                  </span>
                )}
              </p>
            )}
          </div>

          {conflicts.length > 0 && (
            <div className="px-5 py-4">
              <p className="label-micro mb-2.5">Conflict check · {conflicts.length}</p>
              <div className="space-y-2">
                {conflicts.map((conflict, index) => (
                  <div
                    key={index}
                    className={cn("rounded-md border px-3 py-2", conflictTone(conflict.severity))}
                  >
                    <p className="text-[11.5px] font-semibold uppercase tracking-wide">{conflict.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-bone-dim/90">{conflict.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {rationale.length > 0 && (
            <div className="px-5 py-4">
              <p className="label-micro mb-2.5">Why this plan</p>
              <ul className="space-y-1.5">
                {rationale.map((reason, index) => (
                  <li key={index} className="flex gap-2 text-[12px] leading-relaxed text-muted">
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-brass/70" aria-hidden />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {planPreview && planPreview.blocks.length > 0 && (
            <div className="px-5 py-4">
              <div className="mb-2.5 flex items-center justify-between">
                <p className="label-micro">Proposed day · {planPreview.date}</p>
                <span className="text-[10.5px] text-muted">
                  {planPreview.window.label} · {planPreview.stats.tasks_scheduled} task block(s)
                </span>
              </div>
              <div className="space-y-1.5">
                {planPreview.blocks.map((block, index) => (
                  <div
                    key={index}
                    className="flex items-baseline gap-3 rounded border border-line-soft bg-ink-950/50 px-3 py-1.5"
                  >
                    <span className="num w-[92px] shrink-0 font-mono text-[11px] text-muted">
                      {fmtTime(block.start_at, format)}–{fmtTime(block.end_at, format)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-bone-dim">{block.title}</span>
                    <Badge tone={block.type === "event" ? "neutral" : block.type === "study" ? "brass" : "sky"}>
                      {block.type}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {workflow.actions.length > 0 && (
            <div className="px-5 py-4">
              <div className="mb-2.5 flex items-center justify-between">
                <p className="label-micro">Proposed actions</p>
                <span className="text-[10.5px] text-muted">
                  {pending ? "Nothing is written until you approve." : "Decision recorded."}
                </span>
              </div>
              <div className="space-y-2">
                {workflow.actions.map((action) => (
                  <div
                    key={action.id}
                    className={cn(
                      "rounded-md border px-3.5 py-3",
                      action.status === "executed"
                        ? "border-sage/20 bg-sage/[0.03]"
                        : action.status === "rejected"
                          ? "border-clay/20 bg-clay/[0.03]"
                          : action.status === "failed"
                            ? "border-clay/30 bg-clay/[0.05]"
                            : "border-line bg-ink-950/60",
                    )}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex min-w-0 gap-2.5">
                        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded border border-line bg-ink-850 text-brass">
                          {actionIcon(action.action_type)}
                        </span>
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium text-bone">{action.title}</p>
                          <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted">
                            {action.preview?.summary ?? action.description}
                          </p>
                          {action.preview?.reason && (
                            <p className="mt-1 text-[11px] leading-relaxed text-muted/80">{action.preview.reason}</p>
                          )}
                          {action.error && (
                            <p className="mt-1 text-[11.5px] text-clay">{action.error}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                        <StatusBadge status={action.status} />
                        {interactive && pending && action.status === "proposed" && (
                          <>
                            <Button
                              size="sm"
                              variant="primary"
                              loading={busy === `approve-${action.id}`}
                              onClick={() =>
                                run(
                                  `approve-${action.id}`,
                                  () => api.decideAction(workflow.id, action.id, "approve"),
                                  "Action approved. Nothing executed yet.",
                                )
                              }
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() =>
                                run(
                                  `reject-${action.id}`,
                                  () => api.decideAction(workflow.id, action.id, "reject"),
                                  "Action rejected.",
                                )
                              }
                            >
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 pl-[38px]">
                      <span className="font-mono text-[10px] uppercase tracking-wide text-muted/80">
                        {action.provider} · {action.action_type}
                      </span>
                      {workflow.plan.providers?.find((provider) =>
                        provider.key.includes(action.provider),
                      )?.kind === "local" && <SimulationChip />}
                      {action.executed_at && (
                        <span className="text-[10.5px] text-muted">
                          executed {fmtDateTime(action.executed_at, format)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {workflow.actions.length === 0 && workflow.result.tasks && (
            <div className="px-5 py-4">
              <p className="label-micro mb-2.5">Pending tasks · local read-only</p>
              <div className="divide-y divide-line-soft rounded border border-line">
                {workflow.result.tasks.map((task) => (
                  <div key={task.id} className="flex flex-wrap items-center gap-2 px-3 py-2">
                    <span className="min-w-0 flex-1 truncate text-[12px] text-bone-dim">{task.title}</span>
                    <PriorityBadge priority={task.priority} />
                    {task.due_at && (
                      <span className="text-[10.5px] text-muted">due {fmtDateTime(task.due_at, format)}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {workflow.executed_at && (
            <div className="flex flex-wrap items-center gap-2 bg-ink-850/50 px-5 py-3">
              <CheckCheck className="size-4 text-sage" />
              <p className="text-[12px] text-bone-dim">
                Executed {executedCount} action{executedCount === 1 ? "" : "s"} ·{" "}
                {fmtDateTime(workflow.executed_at, format)}
              </p>
              {workflow.result.failures && workflow.result.failures.length > 0 && (
                <span className="text-[11.5px] text-clay">{workflow.result.failures.join(" · ")}</span>
              )}
            </div>
          )}

          {interactive && pending && (
            <div className="flex flex-wrap items-center gap-2 bg-ink-850/70 px-5 py-3.5">
              <Button
                variant="primary"
                size="sm"
                icon={<Play className="size-3.5" />}
                loading={busy === "execute"}
                disabled={approvedCount === 0}
                onClick={() =>
                  run("execute", () => api.executeWorkflow(workflow.id), "Workflow executed. Check Calendar and Activity.")
                }
              >
                Execute approved ({approvedCount})
              </Button>
              <Button
                size="sm"
                icon={<ShieldCheck className="size-3.5" />}
                loading={busy === "approve-all"}
                onClick={() =>
                  run("approve-all", () => api.decideAll(workflow.id, "approve"), "All actions approved. Review, then execute.")
                }
              >
                Approve all
              </Button>
              <Button
                size="sm"
                variant="danger"
                icon={<X className="size-3.5" />}
                loading={busy === "reject-all"}
                onClick={() =>
                  run("reject-all", () => api.decideAll(workflow.id, "reject"), "All actions rejected. Nothing executed.")
                }
              >
                Reject all
              </Button>
              <span className="ml-auto text-[10.5px] leading-relaxed text-muted">
                Execution is one-way; duplicate runs are blocked by the backend.
              </span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
