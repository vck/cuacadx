import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimeValue } from "../types";

interface Props {
  series: TimeValue[];
  lat: number;
  lon: number;
  varLabel: string;
  unit: string;
  onClose: () => void;
}

export default function TimeSeriesChart({
  series,
  lat,
  lon,
  varLabel,
  unit,
  onClose,
}: Props) {
  if (series.length === 0) return null;

  const values = series.map((s) => s.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;

  return (
    <div className="h-56 shrink-0 border-t border-slate-700 bg-slate-950 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-300">
          {varLabel} · {lat.toFixed(2)}°N, {lon.toFixed(2)}°E
        </span>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span>
            min <b className="text-cyan-400">{min.toFixed(1)}</b>
          </span>
          <span>
            max <b className="text-orange-400">{max.toFixed(1)}</b>
          </span>
          <span>
            avg <b className="text-slate-300">{mean.toFixed(1)}</b>
          </span>
          <span className="text-slate-600">{unit}</span>
          <button
            onClick={onClose}
            className="ml-2 rounded px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          >
            ✕
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="ts"
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            width={50}
          />
          <Tooltip
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 6,
              fontSize: 12,
            }}
            labelFormatter={(v: string) => v}
            formatter={(value: number) => [value.toFixed(1), varLabel]}
          />
          <Area
            type="monotone"
            dataKey="v"
            stroke="#06b6d4"
            strokeWidth={1.5}
            fill="url(#fill)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
