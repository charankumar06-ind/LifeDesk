import { useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  FolderOpen,
  ListChecks,
  Mail,
  MessageSquare,
  Search,
  Sparkles,
  Wrench,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import {
  Badge,
  Button,
  Card,
  ErrorPanel,
  PageHeader,
  type BadgeTone,
} from "../components/ui";
import type { AutomationItem, AutomationStatus } from "../lib/types";

const STATUS_META: Record<AutomationStatus, { label: string; tone: BadgeTone }> = {
  ready: { label: "Ready", tone: "sage" },
  needs_setup: { label: "Needs setup", tone: "brass" },
  degraded: { label: "Paused", tone: "clay" },
  planned: { label: "Roadmap", tone: "outline" },
};

const CATEGORY_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  "Daily planning": Sparkles,
  "Focus & time": Zap,
  Calendar: CalendarDays,
  Tasks: ListChecks,
  Reminders: Bell,
  Communication: Mail,
  Research: Search,
  Files: FolderOpen,
};

function CategoryIcon({ category }: { category: string }) {
  const Icon = CATEGORY_ICONS[category] ?? MessageSquare;
  return <Icon className="size-4 text-brass/80" />;
}

function statusCounts(items: AutomationItem[]) {
  return {
    ready: items.filter((item) => item.status === "ready").length,
    setup: items.filter((item) => item.status === "needs_setup").length,
    planned: items.filter((item) => item.status === "planned").length,
  };
}

export default function AutomationsPage() {
  const catalog = useApi(() => api.automations(), []);
  const [filter, setFilter] = useState("all");
  const navigate = useNavigate();

  const data = catalog.data;
  const items = data?.items ?? [];
  const categories = ["all", ...Array.from(new Set(items.map((item) => item.category)))];
  const visible = filter === "all" ? items : items.filter((item) => item.category === filter);
  const counts = statusCounts(items);
  const percentage = data?.summary.working_percentage ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="MCP Automation Catalog"
        title={
          <>
            One catalog.
            <br />
            Every automation.
          </>
        }
        description="These are the tasks LifeDesk can automate through the same MCP tool contract. Readiness is computed from the live provider boundary — nothing here is marked ready unless the backend can actually run it."
        actions={
          <Badge tone={data?.provider_mode === "mcp" ? "sky" : "neutral"} dot>
            {data?.provider_mode === "mcp" ? "MCP mode" : "Local mode"}
          </Badge>
        }
      />

      {catalog.error && <ErrorPanel message={catalog.error} />}

      <Card className="animate-enter mb-4 overflow-hidden">
        <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="label-micro">Working right now</p>
            <p className="mt-1 text-[26px] leading-none text-bone">
              <span className="num">{counts.ready}</span>
              <span className="text-muted"> / {data?.summary.total ?? items.length}</span>
            </p>
            <p className="mt-1.5 text-[11.5px] text-muted">
              {data?.summary.implemented ?? 0} implemented ({data?.summary.implemented_percentage ?? 0}%)
              · {counts.setup} need setup · {counts.planned} on the roadmap
            </p>
          </div>
          <div className="w-full sm:max-w-[320px]">
            <div className="flex items-center justify-between text-[10.5px] text-muted">
              <span>Catalog readiness</span>
              <span className="num font-semibold text-brass">{percentage}%</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full border border-white/[0.06] bg-ink-950">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#6f5bf0,#b6a7ff)]"
                style={{ width: `${percentage}%` }}
              />
            </div>
            <p className="mt-1.5 text-[10.5px] text-muted">
              Writes are still approval-gated; read-only automations execute immediately.
            </p>
          </div>
        </div>
      </Card>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {categories.map((category) => (
          <button
            key={category}
            type="button"
            onClick={() => setFilter(category)}
            className={cn(
              "rounded-full border px-3 py-1 text-[11.5px] transition-colors",
              filter === category
                ? "border-brass/45 bg-brass/15 text-[#c7bcff]"
                : "border-line bg-ink-850 text-muted hover:border-brass/30 hover:text-bone-dim",
            )}
          >
            {category === "all" ? "All" : category}
          </button>
        ))}
      </div>

      {catalog.loading && !data ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-52 animate-pulse rounded-xl bg-ink-850" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((item) => {
            const meta = STATUS_META[item.status];
            const planned = item.status === "planned";
            return (
              <Card
                key={item.id}
                as="article"
                className={cn(
                  "flex flex-col px-4 py-4",
                  planned && "opacity-80",
                  item.status === "degraded" && "border-clay/25",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="flex size-8 items-center justify-center rounded-[9px] border border-white/10 bg-white/[0.035]">
                      <CategoryIcon category={item.category} />
                    </span>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.12em] text-muted">{item.category}</p>
                      <p className="text-[10px] text-muted/70">
                        {item.action === "read" ? "Read-only" : "Approval required"}
                      </p>
                    </div>
                  </div>
                  <Badge tone={meta.tone} dot={item.status === "ready"}>
                    {meta.label}
                  </Badge>
                </div>

                <h3 className="mt-3 text-[15px] leading-tight text-bone">{item.title}</h3>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{item.description}</p>

                <button
                  type="button"
                  onClick={() => navigate("/command", { state: { command: item.example } })}
                  disabled={planned}
                  className="mt-3 w-full rounded-md border border-line bg-ink-950 px-2.5 py-2 text-left font-mono text-[10.5px] leading-relaxed text-bone-dim transition-colors hover:border-brass/35 disabled:cursor-not-allowed disabled:opacity-70"
                  title={planned ? "Roadmap item" : "Load this command in the Command Center"}
                >
                  “{item.example}”
                </button>

                <p className="mt-2 flex-1 text-[10.5px] leading-relaxed text-muted/80">
                  {item.status_detail}
                </p>

                <div className="mt-3 flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1 text-[10px] text-muted">
                    {item.status === "ready" ? (
                      <CheckCircle2 className="size-3 text-sage" />
                    ) : (
                      <Wrench className="size-3" />
                    )}
                    {item.status === "ready" ? "Wired to MCP" : planned ? "Not wired yet" : "Configuration needed"}
                  </span>
                  <Button
                    size="sm"
                    variant={item.status === "ready" ? "primary" : "secondary"}
                    disabled={planned}
                    trailingIcon={<ArrowUpRight className="size-3.5" />}
                    onClick={() => navigate("/command", { state: { command: item.example } })}
                  >
                    {planned ? "Planned" : "Open command"}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10.5px] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <CheckCircle2 className="size-3 text-sage" /> Ready: the active provider exposes the required tools.
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Wrench className="size-3 text-brass" /> Needs setup: credentials or an optional tool are missing.
        </span>
        <span className="inline-flex items-center gap-1.5">
          <FolderOpen className="size-3" /> Roadmap: planned external MCP integration for the hackathon build.
        </span>
      </div>
    </div>
  );
}
