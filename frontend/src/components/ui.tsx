import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { AlertTriangle, ArrowRight, Loader2, RefreshCw, X } from "lucide-react";
import { cn } from "../lib/cn";

/* ------------------------------------------------------------------ Button */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "quiet";
type ButtonSize = "sm" | "md";

const variants: Record<ButtonVariant, string> = {
  primary:
    "border border-white/15 bg-[linear-gradient(135deg,#9d8bff_0%,#6f5bf0_55%,#5b4ae0_100%)] text-white font-semibold shadow-[0_10px_28px_-12px_rgba(124,92,255,0.95),inset_0_1px_0_rgba(255,255,255,0.28)] hover:brightness-110",
  secondary:
    "bg-white/[0.055] text-bone-dim border border-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] hover:border-white/20 hover:bg-white/[0.085] hover:text-bone",
  ghost: "bg-transparent text-muted border border-transparent hover:bg-white/[0.055] hover:text-bone",
  danger:
    "bg-clay/[0.06] text-clay border border-clay/30 hover:bg-clay/[0.12] hover:border-clay/55",
  quiet: "bg-ink-800 text-bone-dim border border-line-soft hover:border-line hover:text-bone",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[12.5px] rounded-lg gap-1.5",
  md: "h-9.5 px-4 text-[13.5px] rounded-[10px] gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
  trailingIcon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  trailingIcon,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap transition-all duration-150",
        "disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading ? <Loader2 className="spin size-3.5" aria-hidden /> : icon}
      {children}
      {!loading && trailingIcon}
    </button>
  );
}

/* -------------------------------------------------------------------- Link */

export function ActionLink({
  onClick,
  children,
  className,
}: {
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 text-[12.5px] font-medium text-brass transition-colors hover:text-[#c7bcff]",
        className,
      )}
    >
      {children}
      <ArrowRight className="size-3.5" aria-hidden />
    </button>
  );
}

/* ------------------------------------------------------------------- Badge */

export type BadgeTone = "neutral" | "brass" | "sage" | "clay" | "sky" | "outline";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "border-white/10 bg-white/[0.05] text-bone-dim",
  brass: "border-brass/30 bg-brass/[0.13] text-[#bdb0ff]",
  sage: "border-sage/25 bg-sage/[0.11] text-sage",
  clay: "border-clay/30 bg-clay/[0.11] text-clay",
  sky: "border-sky/25 bg-sky/[0.11] text-sky",
  outline: "border-white/10 bg-transparent text-muted",
};

export function Badge({
  children,
  tone = "neutral",
  className,
  dot = false,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold tracking-[0.06em] uppercase whitespace-nowrap",
        badgeTones[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------- Card */

export function Card({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return <Tag className={cn("panel", className)}>{children}</Tag>;
}

export function CardHeader({
  title,
  eyebrow,
  action,
  className,
}: {
  title: ReactNode;
  eyebrow?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-4",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && <div className="label-micro mb-1.5">{eyebrow}</div>}
        <h2 className="text-[16px] leading-tight text-bone">{title}</h2>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Labels */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="animate-enter mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <div className="label-micro mb-2.5 flex items-center gap-2">
          <span className="inline-block h-px w-5 bg-gradient-to-r from-brass to-transparent" aria-hidden />
          {eyebrow}
        </div>
        <h1 className="text-[30px] leading-[1.08] tracking-[-0.03em] text-bone sm:text-[37px]">{title}</h1>
        {description && <p className="mt-3 max-w-xl text-[13.5px] leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function SectionTitle({
  title,
  action,
  className,
}: {
  title: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <h3 className="label-micro text-bone-dim">{title}</h3>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------- Inputs */

export function Field({
  label,
  hint,
  error,
  htmlFor,
  children,
  className,
}: {
  label: string;
  hint?: ReactNode;
  error?: string;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-[12px] font-medium text-bone-dim">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-[11.5px] text-clay">{error}</p>
      ) : hint ? (
        <p className="text-[11.5px] leading-relaxed text-muted/80">{hint}</p>
      ) : null}
    </div>
  );
}

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn("field-input", className)} />;
}

export function TextArea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn("field-input leading-relaxed", className)} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={cn("field-input appearance-none pr-8", className)}>
      {children}
    </select>
  );
}

/* ------------------------------------------------------------------- Modal */

export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#05050c]/80 px-4 py-10 backdrop-blur-sm sm:items-center">
      <button
        type="button"
        aria-label="Close dialog"
        onClick={onClose}
        className="fixed inset-0 cursor-default"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "animate-enter panel relative z-10 w-full rounded-2xl shadow-2xl shadow-black/70",
          wide ? "max-w-2xl" : "max-w-lg",
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-4">
          <div>
            <h2 className="text-[18px] leading-tight text-bone">{title}</h2>
            {description && <p className="mt-1 text-[12.5px] text-muted">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-white/[0.07] hover:text-bone"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="px-5 py-5">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-white/[0.06] px-5 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- States etc */

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("spin size-4 text-muted", className)} aria-hidden />;
}

export function LoadingBlock({ rows = 4, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-2.5 p-5" role="status" aria-label={label}>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-10 animate-pulse rounded-lg border border-white/[0.05] bg-white/[0.035]"
          style={{ animationDelay: `${index * 70}ms` }}
        />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
      {icon && (
        <div className="mb-3 flex size-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-muted shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
          {icon}
        </div>
      )}
      <p className="serif text-[16.5px] text-bone">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-[12.5px] leading-relaxed text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border border-clay/25 bg-clay/[0.07] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-clay" aria-hidden />
        <div>
          <p className="text-[13px] font-medium text-bone">That request did not complete</p>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button size="sm" variant="secondary" icon={<RefreshCw className="size-3.5" />} onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- Stat tile */

type Accent = "bone" | "brass" | "sage" | "clay" | "sky";

const accentText: Record<Accent, string> = {
  bone: "text-bone",
  brass: "text-bone",
  sage: "text-bone",
  clay: "text-clay",
  sky: "text-bone",
};

const accentChip: Record<Accent, string> = {
  bone: "border-white/12 bg-white/[0.06] text-bone-dim",
  brass: "border-brass/30 bg-brass/[0.16] text-[#bdb0ff] shadow-[0_0_22px_-6px_rgba(139,124,255,0.7)]",
  sage: "border-sage/30 bg-sage/[0.14] text-sage shadow-[0_0_22px_-8px_rgba(79,214,168,0.8)]",
  clay: "border-clay/30 bg-clay/[0.14] text-clay",
  sky: "border-sky/30 bg-sky/[0.14] text-sky shadow-[0_0_22px_-8px_rgba(92,200,255,0.8)]",
};

export function StatTile({
  label,
  value,
  hint,
  accent = "brass",
  icon,
  delta,
  chart,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  accent?: Accent;
  icon?: ReactNode;
  delta?: ReactNode;
  chart?: ReactNode;
}) {
  return (
    <div className="panel group relative overflow-hidden px-4 py-3.5 transition-colors hover:border-white/[0.16]">
      <div
        className="pointer-events-none absolute -right-10 -top-12 size-28 rounded-full opacity-30 blur-2xl transition-opacity group-hover:opacity-60"
        style={{
          background:
            accent === "sage"
              ? "rgba(79,214,168,0.35)"
              : accent === "sky"
                ? "rgba(92,200,255,0.35)"
                : accent === "clay"
                  ? "rgba(255,125,156,0.3)"
                  : "rgba(139,124,255,0.4)",
        }}
        aria-hidden
      />
      <div className="relative flex items-start justify-between gap-2">
        <span className="label-micro pt-1">{label}</span>
        {icon && <span className={cn("icon-chip shrink-0", accentChip[accent])}>{icon}</span>}
      </div>
      <div className={cn("num relative mt-2.5 text-[28px] leading-none tracking-[-0.02em] font-semibold", accentText[accent])}>
        {value}
      </div>
      {delta && <div className="relative mt-2 text-[11px] font-medium text-sage">{delta}</div>}
      {hint && <div className={cn("relative text-[11.5px] leading-relaxed text-muted", delta ? "mt-1" : "mt-2")}>{hint}</div>}
      {chart && <div className="relative mt-2">{chart}</div>}
    </div>
  );
}

/* ------------------------------------------------------------- Mini charts */

export function MiniAreaChart({
  values,
  height = 56,
  tone = "#9d8bff",
  fillFrom = "rgba(157,139,255,0.34)",
}: {
  values: number[];
  height?: number;
  tone?: string;
  fillFrom?: string;
}) {
  const id = `area-${tone.replace(/[^a-z0-9]/gi, "")}`;
  const max = Math.max(1, ...values);
  const n = values.length;
  const step = n > 1 ? 100 / (n - 1) : 100;
  const points = values.map((value, index) => ({
    x: index * step,
    y: 100 - (value / max) * 82 - 8,
  }));

  let line = "";
  points.forEach((point, index) => {
    if (index === 0) {
      line += `M ${point.x} ${point.y}`;
      return;
    }
    const previous = points[index - 1];
    const midX = (previous.x + point.x) / 2;
    line += ` C ${midX} ${previous.y}, ${midX} ${point.y}, ${point.x} ${point.y}`;
  });
  const area = `${line} L 100 100 L 0 100 Z`;

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className="w-full"
      style={{ height }}
      aria-hidden
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fillFrom} />
          <stop offset="100%" stopColor="rgba(157,139,255,0)" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke={tone}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/* ------------------------------------------------------------ Status badges */

const actionTone: Record<string, BadgeTone> = {
  proposed: "sky",
  approved: "brass",
  rejected: "clay",
  executing: "sky",
  executed: "sage",
  failed: "clay",
  pending_approval: "brass",
  completed: "sage",
  partial: "brass",
  rejected_workflow: "clay",
  success: "sage",
  pending: "sky",
  dismissed: "neutral",
  todo: "neutral",
  in_progress: "sky",
  done: "sage",
  connected: "sage",
  not_configured: "neutral",
  fallback: "brass",
  error: "clay",
  warning: "brass",
  critical: "clay",
  info: "sky",
  skipped: "neutral",
  awaiting_approval: "brass",
};

const actionLabel: Record<string, string> = {
  pending_approval: "Awaiting approval",
  in_progress: "In progress",
  not_configured: "Not configured",
  fallback: "Fallback",
  rejected: "Rejected",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const label = actionLabel[status] ?? status.replace(/_/g, " ");
  return (
    <Badge tone={actionTone[status] ?? "neutral"} dot className={className}>
      {label}
    </Badge>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  const tones: Record<string, { color: string; label: string }> = {
    urgent: { color: "bg-clay", label: "Urgent" },
    high: { color: "bg-brass", label: "High" },
    medium: { color: "bg-sky", label: "Medium" },
    low: { color: "bg-muted/70", label: "Low" },
  };
  const entry = tones[priority] ?? tones.medium;
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] text-bone-dim">
      <span className={cn("size-1.5 rounded-full", entry.color)} aria-hidden />
      {entry.label}
    </span>
  );
}

export function SimulationChip() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/[0.05] px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-muted"
      title="This tool call was executed by a local SQLite provider, not a real MCP server."
    >
      Local simulation
    </span>
  );
}
