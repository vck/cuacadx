interface Props {
  source: string;
  varLabel: string;
  ts: string;
  count: number;
  loading: boolean;
}

export default function InfoBar({ source, varLabel, ts, count, loading }: Props) {
  return (
    <div className="absolute bottom-4 left-4 z-[1000] rounded-lg border border-slate-600 bg-slate-950/90 px-4 py-2 text-xs backdrop-blur-sm flex items-center gap-3">
      {loading && <span className="text-cyan-400">Loading…</span>}
      <span className="text-slate-400">
        {source.toUpperCase()}
      </span>
      <span className="text-slate-300">{varLabel}</span>
      <span className="text-slate-500">{ts}</span>
      <span className="text-slate-500">{count} pts</span>
    </div>
  );
}
