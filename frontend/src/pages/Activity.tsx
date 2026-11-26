import { useState } from "react";
import { ChevronDown, ScrollText, ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
  Select,
  SimulationChip,
  StatTile,
  StatusBadge,
} from "../components/ui";
import { fmtDateTime, humanize, relativeTime } from "../lib/format";
import type { ActivityEntry } from "../lib/types";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "success", label: "Success" },
  { key: "rejected", label: "Rejected" },
  { key: "failed", label: "Failed" },
];

const PROVIDERS = ["calendar", "task", "reminder", "mail", "workflow", "ai"];

const rowAccent: Record<string, string> = {
  success: "border-l-sage/50",
  rejected: "border-l-brass/60",
  failed: "border-l-clay/70",
};

function DetailCell({ entry }: { entry: ActivityEntry }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1 text-[10.5px] text-muted transition-colors hover:text-bone-dim"
      >
        Details
        <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <pre className="mt-2 max-w-[520px] overflow-x-auto rounded border border-line bg-ink-950 p-2 font-mono text-[10.5px] leading-relaxed text-muted">
          {JSON.stringify(entry.detail, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function ActivityPage() {
  const [status, setStatus] = useState("all");
  const [provider, setProvider] = useState("all");
  const activityApi = useApi(
    () =>
      api.activity({
        limit: 200,
        status: status === "all" ? undefined : status,
        provider: provider === "all" ? undefined : provider,
      }),
    [status, provider],
  );
  const systemApi = useApi(() => api.system(), []);
  const system = systemApi.data;
  const providerMode = system?.provider_mode ?? "local";

  const data = activityApi.data;
  const entries = data?.entries ?? [];
  const summary = data?.summary;

  return (
    <div>
      <PageHeader
        eyebrow="Activity Monitor"
        title="Every tool call, on the record."
        description={
          providerMode === "mcp"
            ? `Workflow executions and provider operations with their result. Calls are executing through ${system?.mcp?.transport ?? "MCP"} to ${system?.mcp?.endpoint ?? "the configured MCP server"}.`
            : providerMode === "local-fallback"
              ? "Workflow executions and provider operations with their result. MCP was unavailable at startup, so local SQLite providers are active."
              : "Workflow executions and provider operations with their result. Local simulated calls are labelled; no MCP server is connected."
        }
        actions={
          <Button size="sm" variant="secondary" onClick={activityApi.reload}>
            Refresh
          </Button>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Total entries" value={summary?.total ?? 0} hint="All executed or attempted operations" />
        <StatTile label="Successful" value={summary?.counts.success ?? 0} accent="sage" hint="Provider writes and reads" />
        <StatTile label="Rejected" value={summary?.counts.rejected ?? 0} accent="brass" hint="Blocked at the approval gate" />
        <StatTile label="Failed" value={summary?.counts.failed ?? 0} accent="clay" hint="Provider or validation errors" />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.key}
              type="button"
              onClick={() => setStatus(filter.key)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-[11px] transition-colors",
                status === filter.key
                  ? "border-brass/50 bg-brass/10 text-brass"
                  : "border-line text-muted hover:text-bone-dim",
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <Select
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
          aria-label="Filter by provider"
          className="ml-auto w-auto min-w-[150px]"
        >
          <option value="all">All providers</option>
          {PROVIDERS.map((key) => (
            <option key={key} value={key}>
              {humanize(key)}
            </option>
          ))}
        </Select>
      </div>

      {activityApi.error && <div className="mb-4"><ErrorPanel message={activityApi.error} onRetry={activityApi.reload} /></div>}

      <Card className="animate-enter overflow-hidden">
        <CardHeader
          eyebrow="Execution log"
          title={`${entries.length} operation${entries.length === 1 ? "" : "s"}`}
          action={
            <span className="inline-flex items-center gap-1.5 text-[10.5px] text-muted">
              <ShieldAlert className="size-3.5 text-brass/80" />
              Local simulated providers
            </span>
          }
        />
        {activityApi.loading && !data ? (
          <LoadingBlock rows={7} label="Loading activity" />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<ScrollText className="size-4" />}
            title="No activity for these filters"
            description="Run a workflow or change a filter to see execution history."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[840px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line-soft">
                  {["Timestamp", "Provider", "Operation", "Result", "Status"].map((heading) => (
                    <th key={heading} className="label-micro px-4 py-2.5 font-semibold">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={entry.id}
                    className={cn(
                      "border-b border-line-soft/70 border-l-2 align-top transition-colors last:border-b-0 hover:bg-ink-850/40",
                      rowAccent[entry.status] ?? "border-l-line",
                    )}
                  >
                    <td className="whitespace-nowrap px-4 py-3">
                      <div className="num font-mono text-[11px] text-bone-dim">
                        {fmtDateTime(entry.created_at, "24h")}
                      </div>
                      <div className="mt-0.5 text-[10px] text-muted">{relativeTime(entry.created_at)}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-[11.5px] capitalize text-bone-dim">{entry.provider_type}</div>
                      <div className="mt-0.5 font-mono text-[10px] text-muted">{entry.provider_name}</div>
                      <div className="mt-1">
                        {entry.simulated ? (
                          <SimulationChip />
                        ) : (
                          <Badge tone="sky">External</Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-mono text-[11px] text-bone-dim">{entry.operation}</div>
                      <div className="mt-0.5 text-[10px] text-muted">{humanize(entry.provider_type)} tool call</div>
                    </td>
                    <td className="max-w-[380px] px-4 py-3">
                      <p className="text-[11.5px] leading-relaxed text-muted">{entry.message}</p>
                      <div className="mt-1">
                        <DetailCell entry={entry} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={entry.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <Badge tone={providerMode === "mcp" ? "sky" : providerMode === "local-fallback" ? "brass" : "outline"}>
          {system?.demo_label ?? "Demo Mode — Local Data"}
        </Badge>
        <span>
          {providerMode === "mcp"
            ? `Provider calls use the MCP tool contract over ${system?.mcp?.transport ?? "MCP"}. Approval decisions remain local workflow records.`
            : providerMode === "local-fallback"
              ? "MCP startup failed; provider names such as local-calendar are SQLite adapters and no writes were routed to MCP."
              : "Provider names such as local-calendar are SQLite adapters. Simulation chips mark local calls."}
        </span>
      </div>
    </div>
  );
}
