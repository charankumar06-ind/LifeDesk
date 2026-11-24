import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "../lib/cn";

type Tone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => undefined);

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((message: string, tone: Tone = "success") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id));
    }, 4600);
  }, []);

  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[min(360px,calc(100vw-2.5rem))] flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.id}
            role="status"
            className={cn(
              "animate-toast pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-ink-850 px-3.5 py-3 shadow-xl shadow-black/40",
              item.tone === "error"
                ? "border-clay/40"
                : item.tone === "info"
                  ? "border-sky/35"
                  : "border-sage/35",
            )}
          >
            {item.tone === "error" ? (
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-clay" aria-hidden />
            ) : item.tone === "info" ? (
              <Info className="mt-0.5 size-4 shrink-0 text-sky" aria-hidden />
            ) : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-sage" aria-hidden />
            )}
            <p className="flex-1 text-[12.5px] leading-relaxed text-bone">{item.message}</p>
            <button
              type="button"
              aria-label="Dismiss notification"
              onClick={() => setItems((current) => current.filter((entry) => entry.id !== item.id))}
              className="text-muted transition-colors hover:text-bone"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
