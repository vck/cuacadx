import type { SiteCondition } from "../types";

const SEV_CFG: Record<string, { icon: string; label: string; unit: string }> = {
  rain: { icon: "🌧️", label: "Rain", unit: "mm/24h" },
  wind: { icon: "💨", label: "Wind", unit: "km/h" },
  temp: { icon: "🌡️", label: "Temp", unit: "°C" },
  lightning: { icon: "⚡", label: "Lightning", unit: "km" },
};

function sevColor(level: number): string {
  if (level === 2) return "bg-red-500";
  if (level === 1) return "bg-amber-400";
  return "bg-emerald-500";
}

function sevPulse(level: number): string {
  return level >= 2 ? "animate-pulse" : "";
}

interface Props {
  conditions: SiteCondition | null;
}

export default function OpsStatusBar({ conditions }: Props) {
  if (!conditions) {
    return (
      <div className="flex gap-3 rounded-lg border border-slate-600 bg-slate-950/85 px-4 py-2 text-xs backdrop-blur-sm">
        <span className="text-slate-500">No data</span>
      </div>
    );
  }

  const items = [
    { key: "rain", value: conditions.rain_mm, level: conditions.severities.rain.level },
    { key: "wind", value: conditions.wind_kmh, level: conditions.severities.wind.level },
    { key: "temp", value: conditions.temp_c, level: conditions.severities.temp.level },
    { key: "lightning", value: "—", level: conditions.severities.lightning.level },
  ];

  return (
    <div className="flex gap-1.5 rounded-lg border border-slate-600 bg-slate-950/85 px-3 py-1.5 text-xs backdrop-blur-sm">
      {items.map((item) => {
        const cfg = SEV_CFG[item.key];
        return (
          <div
            key={item.key}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 ${sevPulse(item.level)}`}
          >
            <span>{cfg.icon}</span>
            <span className={`h-2 w-2 rounded-full ${sevColor(item.level)}`} />
            <span className="text-slate-200 font-medium">{item.value}</span>
            <span className="text-slate-500">{cfg.unit}</span>
          </div>
        );
      })}
    </div>
  );
}
