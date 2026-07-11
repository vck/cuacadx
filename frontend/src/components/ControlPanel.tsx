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
  sources,
  source,
  onSourceChange,
  variables,
  varId,
  onVarChange,
  timestamps,
  tsIdx,
  onTsChange,
  playing,
  onPlayToggle,
}: Props) {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-700 bg-slate-950 p-4 flex flex-col gap-4 overflow-y-auto">
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Source</label>
        <select
          className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-2 text-sm"
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
        >
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Variable</label>
        <select
          className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-2 text-sm"
          value={varId}
          onChange={(e) => onVarChange(e.target.value)}
        >
          {variables.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label} ({v.unit})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
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
        <div className="text-xs text-slate-500 mt-1 truncate">
          {timestamps[tsIdx] ?? "—"}
        </div>
      </div>

      <button
        onClick={onPlayToggle}
        className="flex items-center justify-center gap-2 rounded bg-cyan-700 hover:bg-cyan-600 px-4 py-2 text-sm font-medium transition-colors"
      >
        {playing ? "⏸ Pause" : "▶ Play"}
      </button>
    </aside>
  );
}
