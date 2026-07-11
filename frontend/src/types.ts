export interface Source {
  id: string;
  name: string;
  description: string;
  variables: string[];
}

export interface VarInfo {
  id: string;
  label: string;
  unit: string;
}

export interface GridPoint {
  lat: number;
  lon: number;
  v: number;
}

export interface TimeValue {
  ts: string;
  v: number;
}

export interface StormCell {
  cell_id: number;
  centroid_lat: number;
  centroid_lon: number;
  pixel_count: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  polygon: [number, number][];
}

export interface SiteInfo {
  id: string;
  name: string;
  type: string;
  lat: number;
  lon: number;
  thresholds: Record<string, number>;
}

export interface SiteCondition {
  site_id: string;
  site_name: string;
  site_type: string;
  lat: number;
  lon: number;
  temp_c: number;
  wind_kmh: number;
  rain_mm: number;
  pressure_hpa: number;
  humidity_pct: number;
  severities: Record<string, { level: number; label: string }>;
}

export interface Alert {
  ts: string;
  severity: string;
  site: string;
  threat: string;
  message: string;
}

export type LayerId = "rain" | "cells" | "wind" | "sites";
