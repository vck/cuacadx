import { useState } from "react";
import type { Source, VarInfo } from "../types";

interface Props {
  sources: Source[];
  source: string;
  onSourceChange: (s: string) => void;
  variables: VarInfo[];
  varId: string;
  onVarChange: (v: string) => void;
  timestamps: string[];
  tsIdx: number;
  onTsChange: (i: number) => void;
  playing: boolean;
  onPlayToggle: () => void;
}

export default function ControlPanel({
  sources, source, onSourceChange,
  variables, varId, onVarChange,
  timestamps, tsIdx, onTsChange,
  playing, onPlayToggle,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-lg border border-slate-600 bg-slate-950/85 px-3 py-2 text-xs backdrop-blur-sm hover:bg-slate-900 transition-colors"
        title="Data Controls"
      >
        {open ? "✕ Close" : "⚙️ Data"}
      </button>

      {open && (
        <div className="absolute bottom-full right-0 mb-2 w-56 rounded-lg border border-slate-600 bg-slate-950/95 p-3 text-xs backdrop-blur-sm flex flex-col gap-3 shadow-lg">
          <div>
            <label className="block text-[10px] font-medium text-slate-400 mb-1">Source</label>
            <select
              className="w-full rounded bg-slate-800 border border-slate-600 px-2 py-1 text-xs"
              value={source}
              onChange={(e) => onSourceChange(e.target.value)}
            >
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-medium text-slate-400 mb-1">Variable</label>
            <select
              className="w-full rounded bg-slate-800 border border-slate-600 px-2 py-1 text-xs"
              value={varId}
              onChange={(e) => onVarChange(e.target.value)}
            >
              {variables.map((v) => (
                <option key={v.id} value={v.id}>{v.label} ({v.unit})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-medium text-slate-400 mb-1">
              Timestamp ({timestamps.length})
            </label>
            <input
              type="range"
              min={0}
              max={Math.max(0, timestamps.length - 1)}
              value={tsIdx}
              onChange={(e) => onTsChange(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
            <div className="text-[10px] text-slate-500 mt-0.5 truncate">
              {timestamps[tsIdx] ?? "—"}
            </div>
          </div>

          <button
            onClick={onPlayToggle}
            className="flex items-center justify-center gap-1.5 rounded bg-cyan-700 hover:bg-cyan-600 px-3 py-1.5 text-xs font-medium transition-colors"
          >
            {playing ? "⏸ Pause" : "▶ Play"}
          </button>
        </div>
      )}
    </div>
  );
}
