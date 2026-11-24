import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCheck, Inbox, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { Button, Card, EmptyState, ErrorPanel, LoadingBlock, PageHeader } from "../components/ui";
import WorkflowView from "../components/WorkflowView";

export default function ApprovalsPage() {
  const approvals = useApi(() => api.approvals(), []);
  const [tab, setTab] = useState<"pending" | "history">("pending");

  const pending = approvals.data?.pending ?? [];
  const recent = approvals.data?.recent ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Approval Center"
        title="Nothing runs without a decision."
        description="Preview every proposed action, approve or reject it individually, then execute. Approved actions are written to the local providers; rejected ones never run."
        actions={
          <Link to="/command">
            <Button variant="secondary" icon={<ShieldCheck className="size-4" />}>
              New command
            </Button>
          </Link>
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-2 rounded-lg border border-line bg-ink-900 px-4 py-3">
        <ShieldCheck className="size-4 shrink-0 text-brass" />
        <p className="text-[12px] leading-relaxed text-muted">
          Each action carries an idempotency key. The backend refuses to execute a workflow twice, and
          identical actions are blocked at proposal time.
        </p>
        <span className="ml-auto text-[10.5px] whitespace-nowrap text-muted">
          {pending.length} awaiting · {recent.length} archived
        </span>
      </div>

      <div className="mb-4 flex items-center gap-1 border-b border-line">
        {(
          [
            { key: "pending", label: `Pending (${pending.length})` },
            { key: "history", label: "History" },
          ] as const
        ).map((entry) => (
          <button
            key={entry.key}
            type="button"
            onClick={() => setTab(entry.key)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-[12.5px] transition-colors",
              tab === entry.key
                ? "border-brass text-bone"
                : "border-transparent text-muted hover:text-bone-dim",
            )}
          >
            {entry.label}
          </button>
        ))}
      </div>

      {approvals.error && <ErrorPanel message={approvals.error} onRetry={approvals.reload} />}

      {approvals.loading && !approvals.data && (
        <Card>
          <LoadingBlock rows={5} />
        </Card>
      )}

      {approvals.data && tab === "pending" && (
        <div className="space-y-4">
          {pending.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Inbox className="size-4" />}
                title="No workflows awaiting approval"
                description="Run a command such as “Plan my day” and its proposed actions will appear here for review."
                action={
                  <Link to="/command">
                    <Button size="sm" variant="primary">Open command center</Button>
                  </Link>
                }
              />
            </Card>
          ) : (
            pending.map((workflow, index) => (
              <WorkflowView
                key={workflow.id}
                workflow={workflow}
                interactive
                collapsible
                defaultOpen={index === 0}
                onChanged={() => approvals.reload()}
              />
            ))
          )}
        </div>
      )}

      {approvals.data && tab === "history" && (
        <div className="space-y-3">
          {recent.length === 0 ? (
            <Card>
              <EmptyState
                icon={<CheckCheck className="size-4" />}
                title="No decided workflows yet"
                description="Approve, reject or execute a workflow and it will be archived here with its outcome."
              />
            </Card>
          ) : (
            recent.map((workflow) => (
              <WorkflowView
                key={workflow.id}
                workflow={workflow}
                collapsible
                defaultOpen={false}
                onChanged={() => approvals.reload()}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
