interface Props {
  varId: string;
  unit: string;
}

const LEGENDS: Record<string, { label: string; color: string }[]> = {
  t2m: [
    { label: "<22", color: "#0000ff" },
    { label: "22-24", color: "#0088ff" },
    { label: "24-26", color: "#00ccff" },
    { label: "26-28", color: "#00ff88" },
    { label: "28-30", color: "#88ff00" },
    { label: "30-32", color: "#ffcc00" },
    { label: ">32", color: "#ff3300" },
  ],
  d2m: [
    { label: "<20", color: "#1a3a5c" },
    { label: "20-22", color: "#2d5a8a" },
    { label: "22-24", color: "#4a8bc2" },
    { label: "24-26", color: "#7ab8e0" },
    { label: ">26", color: "#b0d8f0" },
  ],
  sp: [
    { label: "<1005", color: "#800026" },
    { label: "1005-08", color: "#bd0026" },
    { label: "1008-10", color: "#e31a1c" },
    { label: "1010-12", color: "#fc4e2a" },
    { label: "1012-14", color: "#fd8d3c" },
    { label: "1014-16", color: "#feb24c" },
    { label: ">1016", color: "#ffffcc" },
  ],
  msl: [
    { label: "<1005", color: "#800026" },
    { label: "1005-08", color: "#bd0026" },
    { label: "1008-10", color: "#e31a1c" },
    { label: "1010-12", color: "#fc4e2a" },
    { label: "1012-14", color: "#fd8d3c" },
    { label: "1014-16", color: "#feb24c" },
    { label: ">1016", color: "#ffffcc" },
  ],
  tp: [
    { label: "<0.001", color: "#ffffff" },
    { label: "0.001-2", color: "#c6dbef" },
    { label: "0.002-5", color: "#6baed6" },
    { label: "0.005-01", color: "#3182bd" },
    { label: "0.01-02", color: "#08519c" },
    { label: ">0.02", color: "#002952" },
  ],
};

export default function Legend({ varId, unit }: Props) {
  const items = LEGENDS[varId] ?? [
    { label: "0-1", color: "#c8e6c9" },
    { label: "1-3", color: "#81c784" },
    { label: "3-5", color: "#4caf50" },
    { label: "5-8", color: "#388e3c" },
    { label: ">8", color: "#1b5e20" },
  ];

  return (
    <div className="absolute bottom-4 right-4 z-[1000] rounded-lg border border-slate-600 bg-slate-950/90 p-3 text-xs backdrop-blur-sm">
      <div className="mb-1 font-medium text-slate-300">
        {varId}{" "}
        <span className="text-slate-500">({unit})</span>
      </div>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ background: item.color }}
          />
          <span className="text-slate-400">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
