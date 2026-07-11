import { useCallback } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from "react-leaflet";
import type { LeafletMouseEvent } from "leaflet";
import type { GridPoint } from "../types";
import type { SelectedPoint } from "../App";

function getColor(val: number, varKey: string): string {
  if (varKey === "bt")
    return val < 220 ? "#ffffff" : val < 240 ? "#ffffcc" : val < 260 ? "#ffcc00" : val < 280 ? "#ff8800" : val < 300 ? "#ff4400" : val < 320 ? "#cc0000" : val < 340 ? "#660000" : "#000000";
  if (varKey === "t2m")
    return val < 22 ? "#0000ff" : val < 24 ? "#0088ff" : val < 26 ? "#00ccff" : val < 28 ? "#00ff88" : val < 30 ? "#88ff00" : val < 32 ? "#ffcc00" : "#ff3300";
  if (varKey === "d2m")
    return val < 20 ? "#1a3a5c" : val < 22 ? "#2d5a8a" : val < 24 ? "#4a8bc2" : val < 26 ? "#7ab8e0" : "#b0d8f0";
  if (varKey === "sp" || varKey === "msl")
    return val < 1005 ? "#800026" : val < 1008 ? "#bd0026" : val < 1010 ? "#e31a1c" : val < 1012 ? "#fc4e2a" : val < 1014 ? "#fd8d3c" : val < 1016 ? "#feb24c" : "#ffffcc";
  if (varKey === "tp")
    return val < 0.001 ? "#ffffff" : val < 0.002 ? "#c6dbef" : val < 0.005 ? "#6baed6" : val < 0.01 ? "#3182bd" : val < 0.02 ? "#08519c" : "#002952";
  const abs = Math.abs(val);
  return abs < 1 ? "#c8e6c9" : abs < 3 ? "#81c784" : abs < 5 ? "#4caf50" : abs < 8 ? "#388e3c" : "#1b5e20";
}

interface ClickHandlerProps {
  onClick: (lat: number, lon: number) => void;
}

function ClickHandler({ onClick }: ClickHandlerProps) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

interface Props {
  points: GridPoint[];
  varId: string;
  onPointClick: (lat: number, lon: number) => void;
  selectedPoint: SelectedPoint | null;
}

export default function WeatherMap({ points, varId, onPointClick, selectedPoint }: Props) {
  const handleCircleClick = useCallback(
    (lat: number, lon: number, e: LeafletMouseEvent) => {
      e.originalEvent.stopPropagation();
      onPointClick(lat, lon);
    },
    [onPointClick],
  );

  return (
    <MapContainer
      center={[0.5, 117]}
      zoom={7}
      zoomControl={false}
      className="h-full w-full"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://openstreetmap.org">OSM</a>'
      />
      <ClickHandler onClick={onPointClick} />

      {points.map((p, i) => {
        const isSelected =
          selectedPoint &&
          Math.abs(p.lat - selectedPoint.lat) < 0.01 &&
          Math.abs(p.lon - selectedPoint.lon) < 0.01;
        return (
          <CircleMarker
            key={i}
            center={[p.lat, p.lon]}
            radius={isSelected ? 10 : 6}
            pathOptions={{
              color: isSelected ? "#fff" : getColor(p.v, varId),
              fillColor: getColor(p.v, varId),
              fillOpacity: 0.85,
              weight: isSelected ? 2 : 0.5,
            }}
            eventHandlers={{
              click: (e) => handleCircleClick(p.lat, p.lon, e),
            }}
          >
            <Popup>{p.v.toFixed(1)}</Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
