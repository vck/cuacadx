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
