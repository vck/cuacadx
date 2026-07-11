interface Props {
  source: string;
  varLabel: string;
  ts: string;
  count: number;
  loading: boolean;
}

export default function InfoBar({ source, varLabel, ts, count, loading }: Props) {
  return (
    <div className="absolute bottom-3 right-20 z-[1000] rounded-lg border border-slate-600 bg-slate-950/75 px-3 py-1.5 text-[10px] backdrop-blur-sm flex items-center gap-2">
      {loading && <span className="text-cyan-400">Loading…</span>}
      <span className="text-slate-500 uppercase">{source}</span>
      <span className="text-slate-300">{varLabel}</span>
      <span className="text-slate-600">{ts}</span>
      <span className="text-slate-600">{count} pts</span>
    </div>
  );
}
