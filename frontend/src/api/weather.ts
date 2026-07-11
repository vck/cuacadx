import type { Alert, GridPoint, SiteCondition, SiteInfo, Source, StormCell, TimeValue, VarInfo } from "../types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function fetchSources(): Promise<{ sources: Source[] }> {
  return get("/sources");
}

export function fetchVariables(source: string): Promise<{ variables: VarInfo[] }> {
  return get(`/sources/${source}/variables`);
}

export function fetchTimestamps(source: string, v: string): Promise<{ timestamps: string[] }> {
  return get(`/sources/${source}/${v}/timestamps`);
}

export function fetchFrame(source: string, v: string, ts: string): Promise<{ points: GridPoint[] }> {
  return get(`/sources/${source}/${v}/frame?ts=${encodeURIComponent(ts)}`);
}

export function fetchCells(source: string, v: string, ts: string): Promise<{ cells: StormCell[] }> {
  return get(`/sources/${source}/${v}/cells?ts=${encodeURIComponent(ts)}`);
}

export function fetchPointSeries(
  source: string,
  v: string,
  lat: number,
  lon: number,
): Promise<{ series: TimeValue[] }> {
  return get(`/sources/${source}/${v}/point?lat=${lat}&lon=${lon}`);
}

// ── Mining Dashboard API ──────────────────────────────────────────

export function fetchSites(): Promise<{ sites: SiteInfo[] }> {
  return get("/sites");
}

export function fetchSiteConditions(): Promise<{ conditions: SiteCondition[] }> {
  return get("/sites/conditions");
}

export function fetchAlerts(): Promise<{ alerts: Alert[] }> {
  return get("/alerts");
}
