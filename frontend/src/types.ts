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
