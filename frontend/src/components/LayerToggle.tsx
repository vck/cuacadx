import type { LayerId } from "../types";

const LAYER_LABELS: Record<LayerId, string> = {
  rain: "Rain",
  cells: "Storm Cells",
  wind: "Wind",
  sites: "Mine Sites",
};

interface Props {
  layers: LayerId[];
  active: Set<LayerId>;
  onToggle: (layer: LayerId) => void;
}

export default function LayerToggle({ layers, active, onToggle }: Props) {
  return (
    <div className="rounded-lg border border-slate-600 bg-slate-950/85 px-3 py-2 text-xs backdrop-blur-sm">
      <div className="text-slate-400 font-medium mb-1.5">Overlays</div>
      {layers.map((layer) => (
        <label key={layer} className="flex items-center gap-2 py-0.5 cursor-pointer hover:text-slate-200">
          <input
            type="checkbox"
            checked={active.has(layer)}
            onChange={() => onToggle(layer)}
            className="accent-cyan-500"
          />
          <span className="text-slate-300">{LAYER_LABELS[layer]}</span>
        </label>
      ))}
    </div>
  );
}
