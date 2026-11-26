import { Outlet, NavLink, useLocation, Link } from "react-router-dom";
import {
  Activity,
  Bell,
  CalendarDays,
  ChevronRight,
  Command,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Route,
  Search,
  Settings as SettingsIcon,
  Zap,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { ComponentType } from "react";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useSettings } from "./SettingsProvider";
import { useAuth } from "./AuthProvider";
import { initials } from "../lib/format";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  badge?: boolean;
}

const primaryNav: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/command", label: "Command Center", icon: Command },
  { to: "/automations", label: "Automations", icon: Zap },
  { to: "/planner", label: "Daily Planner", icon: Route },
];

const secondaryNav: NavItem[] = [
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/tasks", label: "Tasks", icon: ListChecks },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck, badge: true },
  { to: "/activity", label: "Activity", icon: Activity },
];

const routeLabels: Record<string, string> = {
  "/": "Dashboard",
  "/command": "Command Center",
  "/automations": "Automations",
  "/planner": "Daily Planner",
  "/calendar": "Calendar",
  "/tasks": "Tasks",
  "/approvals": "Approvals",
  "/activity": "Activity",
  "/settings": "Settings",
};

function Brand() {
  return (
    <Link to="/" className="group flex items-center gap-2.5">
      <div className="relative flex size-9 items-center justify-center rounded-[11px] border border-white/20 bg-[linear-gradient(140deg,#a493ff_0%,#6f5bf0_55%,#4c3bd1_100%)] shadow-[0_8px_22px_-8px_rgba(124,92,255,0.95),inset_0_1px_0_rgba(255,255,255,0.4)]">
        <Sparkles className="size-[17px] text-white" aria-hidden />
      </div>
      <div>
        <div className="text-[16px] font-semibold leading-none tracking-[-0.02em] text-bone">LifeDesk</div>
        <div className="mt-1 text-[9px] font-semibold uppercase tracking-[0.2em] text-muted">
          Workflow studio
        </div>
      </div>
    </Link>
  );
}

function NavList({ items, pendingCount }: { items: NavItem[]; pendingCount: number }) {
  return (
    <nav className="space-y-1">
      {items.map(({ to, label, icon: Icon, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            cn(
              "group relative flex items-center gap-2.5 rounded-[10px] border px-2.5 py-2 text-[13px] transition-all duration-150",
              isActive
                ? "border-white/[0.09] bg-white/[0.065] text-bone shadow-[inset_0_1px_0_rgba(255,255,255,0.07)]"
                : "border-transparent text-muted hover:bg-white/[0.035] hover:text-bone-dim",
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span
                  className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-gradient-to-b from-[#c4b5fd] to-[#6f5bf0] shadow-[0_0_10px_rgba(157,139,255,0.9)]"
                  aria-hidden
                />
              )}
              <Icon
                className={cn(
                  "size-[16px] transition-colors",
                  isActive ? "text-[#bdb0ff]" : "text-muted/75 group-hover:text-bone-dim",
                )}
              />
              <span className="flex-1">{label}</span>
              {badge && pendingCount > 0 && (
                <span className="num rounded-full border border-brass/35 bg-brass/15 px-1.5 text-[10.5px] leading-[17px] text-[#c7bcff]">
                  {pendingCount}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function Layout() {
  const location = useLocation();
  const { settings } = useSettings();
  const { user, logout } = useAuth();
  const approvals = useApi(() => api.approvals(), [location.pathname]);
  const system = useApi(() => api.system(), []);
  const pendingCount = approvals.data?.pending.length ?? 0;
  const providerMode = system.data?.provider_mode ?? "local";
  const mcpDegraded = providerMode === "mcp" && system.data?.mcp?.status === "error";
  const modeLabel = mcpDegraded
    ? "MCP Degraded — Calls Failing"
    : providerMode === "mcp"
      ? "MCP Mode — Connected"
      : providerMode === "local-fallback"
        ? "MCP fallback — Local Data"
        : "Demo Mode — Local Data";
  const modeDetail = mcpDegraded
    ? "No local fallback · writes return 503 until an MCP call succeeds"
    : providerMode === "mcp"
      ? `${system.data?.mcp?.transport.toUpperCase() ?? "MCP"} provider · approval-gated writes`
      : providerMode === "local-fallback"
        ? "MCP unavailable · SQLite providers active"
        : "SQLite providers · no MCP server connected";

  return (
    <div className="min-h-screen">
      <div className="flex min-h-screen">
        <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-white/[0.06] bg-[#08080f]/60 px-4 py-6 backdrop-blur-xl lg:flex">
          <div className="px-1">
            <Brand />
          </div>

          <div className="mt-9 flex-1">
            <div className="label-micro mb-2 px-2.5">Workspace</div>
            <NavList items={primaryNav} pendingCount={pendingCount} />
            <div className="label-micro mb-2 mt-7 px-2.5">Operations</div>
            <NavList items={secondaryNav} pendingCount={pendingCount} />
          </div>

          <div className="mt-6 space-y-3">
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-[10px] border px-2.5 py-2 text-[13px] transition-colors",
                  isActive
                    ? "border-white/[0.09] bg-white/[0.065] text-bone"
                    : "border-transparent text-muted hover:bg-white/[0.035] hover:text-bone-dim",
                )
              }
            >
              <SettingsIcon className="size-4" />
              Settings
            </NavLink>

            <div className="relative overflow-hidden rounded-xl border border-white/[0.09] bg-[linear-gradient(150deg,rgba(124,92,255,0.16),rgba(255,255,255,0.02))] px-3 py-3">
              <div className="flex items-center gap-2">
                <span className="relative flex size-1.5">
                  <span className={`absolute inline-flex size-full rounded-full opacity-60 ${mcpDegraded ? "bg-clay" : "animate-ping bg-sage"}`} />
                  <span className={`relative inline-flex size-1.5 rounded-full ${mcpDegraded ? "bg-clay" : "bg-sage"}`} />
                </span>
                <span className="text-[11.5px] font-semibold text-bone-dim">{modeLabel}</span>
              </div>
              <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">{modeDetail}</p>
            </div>

            <div className="flex items-center gap-2.5 px-1 pt-1">
              <div className="flex size-8 items-center justify-center rounded-full border border-white/15 bg-[linear-gradient(140deg,#2a2748,#161528)] text-[10.5px] font-semibold text-bone-dim">
                {initials(settings.display_name || "Your profile")}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[12px] text-bone-dim">
                  {settings.display_name || "Your profile"}
                </p>
                <p className="truncate text-[10.5px] text-muted">{settings.workspace || "Personal desk"}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => void logout()}
              className="flex w-full items-center gap-2 rounded-[10px] border border-transparent px-2.5 py-2 text-[12px] text-muted transition-colors hover:border-white/[0.07] hover:bg-white/[0.04] hover:text-bone-dim"
            >
              <LogOut className="size-3.5" />
              Sign out
              <span className="ml-auto truncate font-mono text-[10px] text-muted/70">@{user?.username ?? "owner"}</span>
            </button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="sticky top-0 z-30 hidden items-center gap-3 border-b border-white/[0.06] bg-[#07070f]/70 px-8 py-3 backdrop-blur-xl lg:flex">
            <div className="flex items-center gap-2 text-[11.5px] text-muted">
              <span>Workspace</span>
              <ChevronRight className="size-3 opacity-60" />
              <span className="font-medium text-bone-dim">
                {routeLabels[location.pathname] ?? "LifeDesk"}
              </span>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <Link
                to="/command"
                className="group flex items-center gap-2 rounded-[10px] border border-white/[0.08] bg-white/[0.035] px-3 py-1.5 text-[12px] text-muted transition-colors hover:border-white/20 hover:text-bone-dim"
              >
                <Search className="size-3.5 opacity-70" aria-hidden />
                Ask LifeDesk…
                <span className="ml-6 rounded border border-white/10 bg-white/[0.05] px-1.5 py-px font-mono text-[10px] text-muted/80">
                  open
                </span>
              </Link>

              <Link
                to="/approvals"
                aria-label="Approvals"
                className="relative rounded-[10px] border border-white/[0.08] bg-white/[0.035] p-2 text-muted transition-colors hover:border-white/20 hover:text-bone"
              >
                <Bell className="size-4" />
                {pendingCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-[linear-gradient(140deg,#a493ff,#6f5bf0)] text-[9px] font-bold text-white">
                    {pendingCount}
                  </span>
                )}
              </Link>

              <div className="ml-1 flex items-center gap-2.5 rounded-[10px] border border-white/[0.08] bg-white/[0.035] py-1 pl-1 pr-3">
                <div className="flex size-7 items-center justify-center rounded-lg bg-[linear-gradient(140deg,#3a3168,#1d1a35)] text-[10px] font-semibold text-bone">
                  {initials(settings.display_name || "Your profile")}
                </div>
                <div className="leading-tight">
                  <p className="text-[11.5px] font-medium text-bone-dim">
                    {settings.display_name || "Your profile"}
                  </p>
                  <p className="text-[9.5px] text-muted">{settings.role || "Personal workspace"}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#07070f]/85 backdrop-blur-xl lg:hidden">
            <div className="flex items-center justify-between px-4 py-3">
              <Brand />
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted">
                  {mcpDegraded ? "MCP · degraded" : providerMode === "mcp" ? "MCP" : providerMode === "local-fallback" ? "Fallback" : "Demo"}
                </span>
                <NavLink
                  to="/settings"
                  aria-label="Settings"
                  className="rounded-lg p-1.5 text-muted hover:bg-white/[0.07] hover:text-bone"
                >
                  <SettingsIcon className="size-4" />
                </NavLink>
                <button
                  type="button"
                  onClick={() => void logout()}
                  aria-label="Sign out"
                  className="rounded-lg p-1.5 text-muted hover:bg-white/[0.07] hover:text-bone"
                >
                  <LogOut className="size-4" />
                </button>
              </div>
            </div>
            <div className="flex gap-1 overflow-x-auto px-3 pb-2">
              {[...primaryNav, ...secondaryNav].map(({ to, label, icon: Icon, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11.5px] transition-colors",
                      isActive
                        ? "border-brass/40 bg-brass/15 text-[#c7bcff]"
                        : "border-white/10 text-muted hover:text-bone-dim",
                    )
                  }
                >
                  <Icon className="size-3.5" />
                  {label}
                  {badge && pendingCount > 0 && (
                    <span className="num text-[10px] text-brass">{pendingCount}</span>
                  )}
                </NavLink>
              ))}
            </div>
          </div>

          <main className="mx-auto w-full max-w-[1260px] px-4 py-7 sm:px-7 lg:px-10 lg:py-9">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
