import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchAlerts, fetchCells, fetchFrame, fetchPointSeries, fetchSites, fetchSiteConditions, fetchSources, fetchTimestamps, fetchVariables } from "./api/weather";
import AlertPanel from "./components/AlertPanel";
import ControlPanel from "./components/ControlPanel";
import ForecastTiles, { buildForecast, type DayForecast } from "./components/ForecastTiles";
import InfoBar from "./components/InfoBar";
import LayerToggle from "./components/LayerToggle";
import Legend from "./components/Legend";
import OpsStatusBar from "./components/OpsStatusBar";
import SidebarMetrics from "./components/SidebarMetrics";
import SiteSelector from "./components/SiteSelector";
import TimeSeriesChart from "./components/TimeSeriesChart";
import WeatherMap from "./components/WeatherMap";
import type { Alert, GridPoint, LayerId, SiteCondition, SiteInfo, Source, StormCell, TimeValue, VarInfo } from "./types";

export interface SelectedPoint {
  lat: number;
  lon: number;
}

export default function App() {
  // ── Core weather data ──
  const [sources, setSources] = useState<Source[]>([]);
  const [source, setSource] = useState("fcn");
  const [variables, setVariables] = useState<VarInfo[]>([]);
  const [varId, setVarId] = useState("t2m");
  const [timestamps, setTimestamps] = useState<string[]>([]);
  const [tsIdx, setTsIdx] = useState(0);
  const [points, setPoints] = useState<GridPoint[]>([]);
  const [cells, setCells] = useState<StormCell[]>([]);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);

  // ── Mining dashboard data ──
  const [sites, setSites] = useState<SiteInfo[]>([]);
  const [activeSite, setActiveSite] = useState("bengalon");
  const [conditions, setConditions] = useState<SiteCondition[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  // ── Map interaction ──
  const [selPoint, setSelPoint] = useState<SelectedPoint | null>(null);
  const [series, setSeries] = useState<TimeValue[]>([]);
  const [activeLayers, setActiveLayers] = useState<Set<LayerId>>(new Set(["rain", "cells"]));

  // ── Derived ──
  const currentSiteCondition = useMemo(
    () => conditions.find((c) => c.site_id === activeSite) ?? null,
    [conditions, activeSite],
  );

  // Forecast tiles from current site conditions
  const forecastTiles = useMemo<DayForecast[]>(() => {
    return buildForecast({ t2m: [], rain: [], wind: [] });
  }, []);

  // ── Initial loads ──
  useEffect(() => {
    fetchSources().then((d) => {
      setSources(d.sources);
      if (d.sources.length > 0) setSource(d.sources[0].id);
    });
    fetchSites().then((d) => setSites(d.sites));
    fetchSiteConditions().then((d) => setConditions(d.conditions));
    fetchAlerts().then((d) => setAlerts(d.alerts));
  }, []);

  useEffect(() => {
    if (!source) return;
    setLoading(true);
    fetchVariables(source).then((d) => {
      setVariables(d.variables);
      if (d.variables.length > 0) setVarId(d.variables[0].id);
    });
  }, [source]);

  useEffect(() => {
    if (!source || !varId) return;
    setLoading(true);
    fetchTimestamps(source, varId).then((d) => {
      setTimestamps(d.timestamps);
      setTsIdx(0);
    });
  }, [source, varId]);

  // ── Refresh mining data periodically ──
  useEffect(() => {
    const id = setInterval(() => {
      fetchSiteConditions().then((d) => setConditions(d.conditions));
      fetchAlerts().then((d) => setAlerts(d.alerts));
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const loadFrame = useCallback((src: string, v: string, ts: string) => {
    fetchFrame(src, v, ts).then((d) => {
      setPoints(d.points);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!source || !varId || timestamps.length === 0) return;
    const ts = timestamps[tsIdx];
    if (!ts) return;
    loadFrame(source, varId, ts);
    if (source === "himawari9" && varId === "bt" && ts) {
      fetchCells(source, varId, ts).then((d) => setCells(d.cells));
    } else {
      setCells([]);
    }
  }, [source, varId, tsIdx, timestamps, loadFrame]);

  useEffect(() => {
    if (!playing || timestamps.length === 0) return;
    const id = setInterval(() => setTsIdx((i) => (i + 1) % timestamps.length), 500);
    return () => clearInterval(id);
  }, [playing, timestamps]);

  const handlePointClick = useCallback((lat: number, lon: number) => {
    setSelPoint({ lat, lon });
    fetchPointSeries(source, varId, lat, lon).then((d) => setSeries(d.series));
  }, [source, varId]);

  const handleLayerToggle = useCallback((layer: LayerId) => {
    setActiveLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return next;
    });
  }, []);

  const currentVar = variables.find((v) => v.id === varId);

  return (
    <div className="h-full flex flex-col bg-slate-900 text-slate-100">
      {/* ── Header ── */}
      <header className="flex items-center gap-4 px-5 py-2 border-b border-slate-700 bg-slate-950 shrink-0">
        <span className="text-lg font-bold tracking-tight text-cyan-400">CUACADX</span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">7‑Day Weather Intelligence</span>
        <div className="flex-1" />
        <SiteSelector sites={sites} selected={activeSite} onChange={setActiveSite} />
        <div className="w-px h-5 bg-slate-700" />
        <OpsStatusBar conditions={currentSiteCondition} />
      </header>

      {/* ── Main area: map + overlays ── */}
      <div className="flex-1 relative">
        <WeatherMap
          points={points}
          cells={activeLayers.has("cells") ? cells : []}
          varId={varId}
          onPointClick={handlePointClick}
          selectedPoint={selPoint}
          showSites={activeLayers.has("sites")}
          sites={sites}
          activeSite={activeSite}
        />

        {/* Floating overlays */}
        <div className="absolute top-3 left-3 z-[1000] flex flex-col gap-2">
          <LayerToggle
            layers={["rain", "cells", "wind", "sites"]}
            active={activeLayers}
            onToggle={handleLayerToggle}
          />
          <SidebarMetrics conditions={currentSiteCondition} />
        </div>

        <div className="absolute top-3 right-3 z-[1000]">
          <Legend varId={varId} unit={currentVar?.unit ?? ""} />
        </div>

        <div className="absolute bottom-3 left-3 z-[1000]">
          <AlertPanel alerts={alerts} />
        </div>

        <InfoBar
          source={source}
          varLabel={currentVar?.label ?? varId}
          ts={timestamps[tsIdx] ?? ""}
          count={points.length}
          loading={loading}
        />

        {/* Control panel (collapsed into bottom-right icon) */}
        <div className="absolute bottom-3 right-3 z-[1000] flex gap-2 items-end">
          <ControlPanel
            sources={sources}
            source={source}
            onSourceChange={setSource}
            variables={variables}
            varId={varId}
            onVarChange={setVarId}
            timestamps={timestamps}
            tsIdx={tsIdx}
            onTsChange={setTsIdx}
            playing={playing}
            onPlayToggle={() => setPlaying((p) => !p)}
          />
        </div>
      </div>

      {/* ── Bottom panel ── */}
      {selPoint && series.length > 0 ? (
        <TimeSeriesChart
          series={series}
          lat={selPoint.lat}
          lon={selPoint.lon}
          varLabel={currentVar?.label ?? varId}
          unit={currentVar?.unit ?? ""}
          onClose={() => { setSelPoint(null); setSeries([]); }}
        />
      ) : null}
    </div>
  );
}
