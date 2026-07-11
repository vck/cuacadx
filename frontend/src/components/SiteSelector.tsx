import type { SiteInfo } from "../types";

interface Props {
  sites: SiteInfo[];
  selected: string;
  onChange: (id: string) => void;
}

export default function SiteSelector({ sites, selected, onChange }: Props) {
  if (sites.length === 0) return null;

  const current = sites.find((s) => s.id === selected);
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400">Site</span>
      <select
        className="rounded bg-slate-800 border border-slate-600 px-2 py-1 text-sm font-medium text-slate-100"
        value={selected}
        onChange={(e) => onChange(e.target.value)}
      >
        {sites.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      {current && (
        <span className="text-[10px] text-slate-500">
          {current.type} · {current.lat.toFixed(1)}°S, {current.lon.toFixed(1)}°E
        </span>
      )}
    </div>
  );
}
