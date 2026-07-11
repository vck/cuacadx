import { useCallback, useEffect, useState } from "react";
import { fetchCells, fetchFrame, fetchPointSeries, fetchSources, fetchTimestamps, fetchVariables } from "./api/weather";
import ControlPanel from "./components/ControlPanel";
import InfoBar from "./components/InfoBar";
import Legend from "./components/Legend";
import TimeSeriesChart from "./components/TimeSeriesChart";
import WeatherMap from "./components/WeatherMap";
import type { GridPoint, Source, StormCell, TimeValue, VarInfo } from "./types";

export interface SelectedPoint {
  lat: number;
  lon: number;
}

export default function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [source, setSource] = useState("era5");
  const [variables, setVariables] = useState<VarInfo[]>([]);
  const [varId, setVarId] = useState("t2m");
  const [timestamps, setTimestamps] = useState<string[]>([]);
  const [tsIdx, setTsIdx] = useState(0);
  const [points, setPoints] = useState<GridPoint[]>([]);
  const [cells, setCells] = useState<StormCell[]>([]);
  const [playing, setPlaying] = useState(false);
  const [selPoint, setSelPoint] = useState<SelectedPoint | null>(null);
  const [series, setSeries] = useState<TimeValue[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSources().then((d) => {
      setSources(d.sources);
      if (d.sources.length > 0) setSource(d.sources[0].id);
    });
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

  const loadFrame = useCallback(
    (src: string, v: string, ts: string) => {
      fetchFrame(src, v, ts).then((d) => {
        setPoints(d.points);
        setLoading(false);
      });
    },
    [],
  );

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
    const id = setInterval(() => {
      setTsIdx((i) => (i + 1) % timestamps.length);
    }, 500);
    return () => clearInterval(id);
  }, [playing, timestamps]);

  const handlePointClick = useCallback(
    (lat: number, lon: number) => {
      setSelPoint({ lat, lon });
      fetchPointSeries(source, varId, lat, lon).then((d) => {
        setSeries(d.series);
      });
    },
    [source, varId],
  );

  const currentVar = variables.find((v) => v.id === varId);

  return (
    <div className="h-full flex flex-col bg-slate-900 text-slate-100">
      <header className="flex items-center gap-3 px-5 py-3 border-b border-slate-700 bg-slate-950 shrink-0">
        <span className="text-lg font-bold">☀ CUACADX</span>
        <span className="text-sm text-slate-400">Regional Weather Intelligence</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
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

        <div className="flex-1 relative">
          <WeatherMap
            points={points}
            cells={cells}
            varId={varId}
            onPointClick={handlePointClick}
            selectedPoint={selPoint}
          />
          <Legend varId={varId} unit={currentVar?.unit ?? ""} />
          <InfoBar
            source={source}
            varLabel={currentVar?.label ?? varId}
            ts={timestamps[tsIdx] ?? ""}
            count={points.length}
            loading={loading}
          />
        </div>
      </div>

      {selPoint && (
        <TimeSeriesChart
          series={series}
          lat={selPoint.lat}
          lon={selPoint.lon}
          varLabel={currentVar?.label ?? varId}
          unit={currentVar?.unit ?? ""}
          onClose={() => {
            setSelPoint(null);
            setSeries([]);
          }}
        />
      )}
    </div>
  );
}
