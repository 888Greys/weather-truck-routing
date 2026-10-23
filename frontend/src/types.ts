export type RiskLevel = 0 | 1 | 2 | 3 | 4;

export interface LatLon {
  lat: number;
  lon: number;
  label?: string;
}

export interface Checkpoint {
  miles: number;
  lat: number;
  lon: number;
  eta: string;
  segment_miles: number;
  wind_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
  temp_c: number;
  weather_code: number;
  level: RiskLevel;
  level_label: string;
  driver: string;
  reasons: string[];
  load_escalated: boolean;
  weather_available: boolean;
}

export interface RouteMetrics {
  severe_miles: number;
  high_miles: number;
  moderate_miles: number;
  low_miles: number;
  no_travel_miles: number;
  avg_risk: number;
  peak_level: RiskLevel;
  peak_label: string;
  worst_checkpoint_miles: number | null;
}

export interface RouteOption {
  id: string;
  rank: number;
  label: string;
  is_recommended: boolean;
  source: string;
  distance_miles: number;
  duration_hours: number;
  delta_vs_fastest_miles: number;
  geometry: [number, number][];
  checkpoints: Checkpoint[];
  metrics: RouteMetrics;
  summary: string;
}

export interface HeatCell {
  lat: number;
  lon: number;
  miles: number;
  levels: RiskLevel[];
}

export interface Heatmap {
  horizon_hours: number;
  spacing_miles: number;
  hours: string[];
  routes: Record<string, { cells: HeatCell[] }>;
}

export interface LegendEntry {
  level: RiskLevel;
  label: string;
  color: string;
}

export interface PlanResponse {
  generated_at: string;
  request: {
    origin: LatLon;
    destination: LatLon;
    depart_at: string;
    weight_lb: number;
    sample_interval_miles: number;
    horizon_hours: number;
    scenario: "live" | "stress";
  };
  routes: RouteOption[];
  recommendation: {
    route_id: string;
    label: string;
    rationale: string[];
    ranking: { route_id: string; label: string; rank: number; why: string }[];
  };
  heatmap: Heatmap;
  legend: LegendEntry[];
  meta: {
    routing_provider: string;
    weather_provider: string;
    scenario: string;
    degraded: { routing: boolean; weather: boolean };
    checkpoints_per_route: number[];
  };
}

export interface GeocodeResult {
  label: string;
  name: string;
  lat: number;
  lon: number;
  type: string;
}

export interface PlanRequest {
  origin: LatLon;
  destination: LatLon;
  depart_at: string;
  weight_lb: number;
  sample_interval_miles: number;
  horizon_hours: number;
  scenario: "live" | "stress";
}
