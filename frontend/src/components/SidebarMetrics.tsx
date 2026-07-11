import type { SiteCondition } from "../types";

interface Props {
  conditions: SiteCondition | null;
}

function Badge({ level, label }: { level: number; label: string }) {
  const colors = ["bg-emerald-500/20 text-emerald-400", "bg-amber-400/20 text-amber-300", "bg-red-500/20 text-red-400"];
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[level] || colors[0]}`}>{label}</span>;
}

export default function SidebarMetrics({ conditions }: Props) {
  if (!conditions) {
    return (
      <div className="w-48 rounded-lg border border-slate-600 bg-slate-950/85 p-3 text-xs backdrop-blur-sm">
        <div className="text-slate-500">Select a site</div>
      </div>
    );
  }

  const metrics = [
    { label: "Temperature", value: `${conditions.temp_c}°C`, badge: Badge({ level: conditions.severities.temp.level, label: conditions.severities.temp.label }) },
    { label: "Wind", value: `${conditions.wind_kmh} km/h`, badge: Badge({ level: conditions.severities.wind.level, label: conditions.severities.wind.label }) },
    { label: "Rain (24h)", value: `${conditions.rain_mm} mm`, badge: Badge({ level: conditions.severities.rain.level, label: conditions.severities.rain.label }) },
    { label: "Lightning", value: "—", badge: Badge({ level: conditions.severities.lightning.level, label: conditions.severities.lightning.label }) },
    { label: "Pressure", value: `${conditions.pressure_hpa} hPa` },
    { label: "Humidity", value: `${conditions.humidity_pct}%` },
  ];

  return (
    <div className="w-48 rounded-lg border border-slate-600 bg-slate-950/85 p-3 text-xs backdrop-blur-sm">
      <div className="font-medium text-slate-300 mb-2 flex items-center gap-2">
        <span className="text-cyan-400">◈</span>
        {conditions.site_name}
        <span className="text-slate-500 font-normal">{conditions.site_type}</span>
      </div>
      <div className="flex flex-col gap-1.5">
        {metrics.map((m) => (
          <div key={m.label} className="flex items-center justify-between">
            <span className="text-slate-400">{m.label}</span>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-200 font-medium">{m.value}</span>
              {m.badge}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
