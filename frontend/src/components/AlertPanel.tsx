import { useEffect, useRef, useState } from "react";
import type { Alert } from "../types";

const SEV_CLASS: Record<string, string> = {
  alert: "border-l-red-500 bg-red-950/30",
  caution: "border-l-amber-400 bg-amber-950/20",
  ok: "border-l-emerald-500 bg-emerald-950/10",
};

interface Props {
  alerts: Alert[];
}

export default function AlertPanel({ alerts }: Props) {
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  const visible = alerts.filter((_, i) => !dismissed.has(i));
  const alertCount = alerts.length - dismissed.size;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [visible.length]);

  if (visible.length === 0) {
    return (
      <div className="rounded-lg border border-slate-600 bg-slate-950/75 px-3 py-2 text-xs backdrop-blur-sm flex items-center gap-2">
        <span className="text-emerald-400">✓</span>
        <span className="text-slate-500">No active alerts</span>
        {dismissed.size > 0 && (
          <button
            onClick={() => setDismissed(new Set())}
            className="ml-auto text-slate-600 hover:text-slate-400"
          >
            ↺ restore
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="w-80 rounded-lg border border-slate-600 bg-slate-950/85 text-xs backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-1.5">
        <span className="font-medium text-slate-300">
          Alerts
          {dismissed.size > 0 && <span className="text-slate-500 ml-1 font-normal">({alertCount})</span>}
        </span>
        <div className="flex gap-2">
          {dismissed.size > 0 && (
            <button
              onClick={() => setDismissed(new Set())}
              className="text-slate-600 hover:text-slate-400 text-[10px]"
            >
              ↺ restore
            </button>
          )}
          <button
            onClick={() => setDismissed(new Set(alerts.map((_, i) => i)))}
            className="text-slate-600 hover:text-slate-300"
            title="Dismiss all"
          >
            ✕ all
          </button>
        </div>
      </div>
      <div ref={scrollRef} className="max-h-32 overflow-y-auto">
        {visible.map((a, i) => {
          const origIndex = alerts.findIndex((alert, idx) => !dismissed.has(idx) && alert === a);
          return (
            <div
              key={origIndex}
              className={`border-l-2 px-3 py-1.5 flex items-start gap-2 ${SEV_CLASS[a.severity] || "border-l-slate-600"}`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={a.severity === "alert" ? "text-red-400 font-medium" : "text-amber-300"}>
                    {a.severity === "alert" ? "🔴" : "🟡"}
                  </span>
                  <span className="text-slate-300 truncate">{a.message}</span>
                </div>
                <div className="text-slate-600 mt-0.5">{a.ts} · {a.site}</div>
              </div>
              <button
                onClick={() => setDismissed((prev) => new Set([...prev, origIndex]))}
                className="shrink-0 text-slate-600 hover:text-slate-300 mt-0.5"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
