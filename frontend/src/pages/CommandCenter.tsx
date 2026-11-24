import { useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, CornerDownLeft, Cpu, ShieldCheck, Sparkles, TerminalSquare } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { fmtDate, relativeTime } from "../lib/format";
import { useApi } from "../lib/useApi";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, CardHeader, ErrorPanel, PageHeader, StatusBadge, TextArea } from "../components/ui";
import WorkflowView from "../components/WorkflowView";
import type { Workflow } from "../lib/types";

const EXAMPLES = [
  {
    label: "Plan my day",
    command:
      "Plan my day. I have two pending assignments and need a two-hour Python study session.",
  },
  { label: "Show pending tasks", command: "Show pending tasks" },
  { label: "Study session", command: "Schedule a two-hour Python study session" },
  { label: "Create a reminder", command: "Remind me to submit the course form at 17:00" },
];

const STEPS = [
  { title: "Interpret", detail: "Keyword rules map the request to a supported intent. No model is called." },
  { title: "Read local data", detail: "Calendar and task providers return real rows from SQLite." },
  { title: "Plan & approve", detail: "Actions are proposed, then executed only after approval." },
];

export default function CommandCenter() {
  const [command, setCommand] = useState("");
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const toast = useToast();
  const system = useApi(() => api.system(), []);
  const recent = useApi(() => api.workflows({ limit: 6 }), [workflow?.id]);

  const submit = async () => {
    const trimmed = command.trim();
    if (!trimmed) {
      setError("Enter a command before running the workflow.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.runCommand(trimmed);
      setWorkflow(result);
      toast(
        result.status === "pending_approval"
          ? "Plan ready. Review and approve the proposed actions."
          : result.status === "completed"
            ? "Read-only request completed."
            : "The workflow did not produce actions.",
        result.status === "failed" ? "info" : "success",
      );
      window.setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "The command could not be processed.";
      setError(message);
      toast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (!busy) void submit();
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="AI Command Center"
        title={
          <>
            Describe the day.
            <br />
            Approve the plan.
          </>
        }
        description="Natural language in, an inspectable workflow out. LifeDesk interprets the request with deterministic rules, reads local providers, and waits for your approval before anything changes."
        actions={
          <Badge tone="brass" dot>
            {system.data?.ai.llm_configured ? "LLM configured" : "No LLM configured"}
          </Badge>
        }
      />

      <div className="grid items-start gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card className="animate-enter overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-5 py-3">
            <div className="flex items-center gap-2">
              <TerminalSquare className="size-4 text-brass" />
              <span className="label-micro text-bone-dim">Command</span>
            </div>
            <span className="text-[10.5px] text-muted">
              {system.data?.ai.label ?? "Deterministic intent interpreter"}
            </span>
          </div>

          <div className="p-5">
            <label htmlFor="command-input" className="sr-only">
              Natural language command
            </label>
            <TextArea
              id="command-input"
              rows={4}
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Plan my day. I have two pending assignments and need a two-hour Python study session."
              className="min-h-[104px] resize-y border-line bg-ink-950 text-[14px] leading-relaxed"
            />

            {error && <div className="mt-3"><ErrorPanel message={error} /></div>}

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[11px] text-muted">
                <Cpu className="size-3.5 text-brass/70" />
                Deterministic rules · nothing claims to be an LLM
                <span className="hidden text-line sm:inline">·</span>
                <span className="hidden items-center gap-1 sm:inline-flex">
                  <CornerDownLeft className="size-3" /> Ctrl + Enter
                </span>
              </div>
              <Button
                variant="primary"
                loading={busy}
                icon={<Sparkles className="size-4" />}
                onClick={submit}
                disabled={!command.trim()}
              >
                Run workflow
              </Button>
            </div>

            <div className="mt-4 border-t border-line-soft pt-3">
              <p className="label-micro mb-2">Try a demo command</p>
              <div className="flex flex-wrap gap-1.5">
                {EXAMPLES.map((example) => (
                  <button
                    key={example.label}
                    type="button"
                    onClick={() => {
                      setCommand(example.command);
                      setError(null);
                    }}
                    className="rounded-full border border-line bg-ink-850 px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-brass/40 hover:text-bone-dim"
                  >
                    {example.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="animate-enter px-5 py-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-brass" />
              <span className="label-micro text-bone-dim">Approval gate</span>
            </div>
            <p className="mt-2 text-[12px] leading-relaxed text-muted">
              Proposed actions are previewed, logged and blocked from execution until you approve them.
              Identical actions and repeated executions are rejected by the backend.
            </p>
            <Link
              to="/approvals"
              className="mt-2 inline-flex items-center gap-1 text-[11.5px] text-brass hover:underline"
            >
              Open approval center <ArrowUpRight className="size-3" />
            </Link>
          </Card>

          <Card className="animate-enter overflow-hidden">
            <CardHeader
              eyebrow="Recent"
              title="Command history"
              action={
                <Link to="/activity" className="text-[11.5px] text-brass hover:underline">
                  Activity
                </Link>
              }
            />
            {recent.loading && !recent.data ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="h-12 animate-pulse rounded-md bg-ink-850" />
                ))}
              </div>
            ) : recent.data && recent.data.workflows.length > 0 ? (
              <div className="divide-y divide-line-soft">
                {recent.data.workflows.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setWorkflow(item)}
                    className={cn(
                      "block w-full px-5 py-3 text-left transition-colors hover:bg-ink-850/60",
                      workflow?.id === item.id && "bg-ink-850/80",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[12px] text-bone-dim">{item.intent_label}</span>
                      <StatusBadge status={item.status} />
                    </div>
                    <p className="mt-1 truncate text-[11px] text-muted">{item.command}</p>
                    <p className="mt-0.5 text-[10px] text-muted/70">{relativeTime(item.created_at)}</p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="px-5 py-6 text-center text-[12px] text-muted">No commands yet.</p>
            )}
          </Card>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {STEPS.map((step, index) => (
          <div key={step.title} className="panel flex gap-3 px-4 py-3">
            <span className="num serif text-[13px] text-brass/80">0{index + 1}</span>
            <div>
              <p className="text-[12px] font-medium text-bone-dim">{step.title}</p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{step.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div ref={resultRef} className="mt-6 scroll-mt-6">
        {workflow ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="serif text-[20px] text-bone">Workflow result</h2>
                <p className="mt-0.5 text-[11.5px] text-muted">
                  {fmtDate(workflow.created_at, { day: "numeric", month: "long", year: "numeric" })} ·{" "}
                  {workflow.actions.length} proposed action(s)
                </p>
              </div>
              {workflow.status === "pending_approval" && (
                <Link to="/approvals">
                  <Button size="sm" variant="secondary" trailingIcon={<ArrowUpRight className="size-3.5" />}>
                    Review in Approval Center
                  </Button>
                </Link>
              )}
            </div>
            <WorkflowView
              workflow={workflow}
              interactive
              onChanged={(updated) => {
                setWorkflow(updated);
                recent.reload();
              }}
            />
          </div>
        ) : (
          <Card className="animate-enter border-dashed px-6 py-10 text-center">
            <Sparkles className="mx-auto size-5 text-brass/60" />
            <p className="serif mt-3 text-[18px] text-bone">No workflow running</p>
            <p className="mx-auto mt-1 max-w-md text-[12px] leading-relaxed text-muted">
              Run a command to see the interpreted intent, the plan steps, conflict findings, and the
              actions waiting for approval.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
