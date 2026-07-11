interface DayForecast {
  day: number;
  date: string;
  icon: string;
  tempMax: number;
  tempMin: number;
  precip: number;
  windMax: number;
  severity: number;
}

const ICONS = ["☀️", "🌤️", "⛅", "☁️", "🌧️", "☔", "⛈️"];

interface Props {
  forecast: DayForecast[];
}

export default function ForecastTiles({ forecast }: Props) {
  if (forecast.length === 0) return null;

  return (
    <div className="flex gap-2">
      {forecast.map((day) => (
        <div
          key={day.day}
          className={`flex flex-col items-center rounded-lg border px-3 py-2 text-center text-xs min-w-[80px] ${
            day.severity >= 2
              ? "border-red-500/50 bg-red-950/20"
              : day.severity === 1
                ? "border-amber-400/50 bg-amber-950/20"
                : "border-slate-600 bg-slate-950/50"
          }`}
        >
          <span className="text-slate-500 text-[10px]">Day {day.day}</span>
          <span className="text-lg my-0.5">{day.icon}</span>
          <span className="text-slate-200 font-medium">{day.tempMax.toFixed(0)}°</span>
          <span className="text-slate-500">{day.precip.toFixed(0)}mm</span>
          <span className="text-slate-600 text-[10px]">{day.windMax.toFixed(0)}km/h</span>
        </div>
      ))}
    </div>
  );
}

export type { DayForecast };

export function buildForecast(data: Record<string, number[]>): DayForecast[] {
  const days: DayForecast[] = [];
  for (let d = 0; d < 7; d++) {
    const offset = d * 4; // 4 x 6h steps per day
    const temps = [];
    const precip = [];
    const winds = [];
    for (let h = 0; h < 4; h++) {
      const idx = offset + h;
      if (idx >= 28) break;
      temps.push(data.t2m?.[idx] ?? 300);
      precip.push(data.rain?.[idx] ?? 0);
      winds.push(data.wind?.[idx] ?? 0);
    }

    const tMax = Math.max(...temps.map((t: number) => t - 273.15));
    const tMin = Math.min(...temps.map((t: number) => t - 273.15));
    const pSum = precip.reduce((a: number, b: number) => a + b, 0);
    const wMax = Math.max(...winds);

    let severity = 0;
    if (pSum > 50) severity = 2;
    else if (pSum > 20) severity = 1;
    if (wMax > 35) severity = Math.max(severity, 2);
    else if (wMax > 20) severity = Math.max(severity, 1);

    const iconIdx = pSum > 30 ? 5 : pSum > 10 ? 4 : wMax > 30 ? 3 : tMax > 32 ? 0 : 2;
    days.push({
      day: d + 1,
      date: `D${d + 1}`,
      icon: ICONS[Math.min(iconIdx, ICONS.length - 1)],
      tempMax: tMax,
      tempMin: tMin,
      precip: pSum,
      windMax: wMax,
      severity,
    });
  }
  return days;
}
