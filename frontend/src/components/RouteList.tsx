import type { RouteMetrics, RouteOption } from "../types";
import { formatHours, LEVELS } from "../lib/risk";

interface Props {
  routes: RouteOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function RiskBar({ metrics }: { metrics: RouteMetrics }) {
  const segments: { key: keyof typeof LEVELS; miles: number }[] = [
    { key: 4, miles: metrics.no_travel_miles },
    { key: 3, miles: metrics.severe_miles },
    { key: 2, miles: metrics.high_miles },
    { key: 1, miles: metrics.moderate_miles },
    { key: 0, miles: metrics.low_miles },
  ];
  const total = segments.reduce((sum, segment) => sum + segment.miles, 0) || 1;
  return (
    <div className="risk-bar" role="img" aria-label="Risk mix along the route">
      {segments
        .filter((segment) => segment.miles > 0)
        .map((segment) => (
          <span
            key={segment.key}
            style={{
              width: `${(segment.miles / total) * 100}%`,
              background: LEVELS[segment.key].color,
            }}
            title={`${LEVELS[segment.key].label}: ${segment.miles.toFixed(0)} mi`}
          />
        ))}
    </div>
  );
}

export function RouteList({ routes, selectedId, onSelect }: Props) {
  return (
    <div className="route-list">
      {routes.map((route) => {
        const selected = route.id === selectedId;
        return (
          <button
            key={route.id}
            type="button"
            className={`route-card${selected ? " selected" : ""}${route.is_recommended ? " recommended" : ""}`}
            onClick={() => onSelect(route.id)}
            aria-pressed={selected}
          >
            <div className="route-card-head">
              <span className="rank">#{route.rank}</span>
              <h3>{route.label}</h3>
              {route.is_recommended && <span className="badge">Recommended</span>}
            </div>

            <div className="route-card-stats">
              <div>
                <strong>{formatHours(route.duration_hours)}</strong>
                <span>drive time</span>
              </div>
              <div>
                <strong>{route.distance_miles.toFixed(0)} mi</strong>
                <span>
                  {route.delta_vs_fastest_miles > 0.5
                    ? `+${route.delta_vs_fastest_miles.toFixed(0)} mi vs fastest`
                    : "shortest distance"}
                </span>
              </div>
            </div>

            <RiskBar metrics={route.metrics} />

            <dl className="route-metrics">
              <div>
                <dt>Severe</dt>
                <dd className={route.metrics.severe_miles > 0 ? "warn" : ""}>
                  {route.metrics.severe_miles.toFixed(0)} mi
                </dd>
              </div>
              <div>
                <dt>High</dt>
                <dd className={route.metrics.high_miles > 0 ? "warn" : ""}>
                  {route.metrics.high_miles.toFixed(0)} mi
                </dd>
              </div>
              <div>
                <dt>No travel</dt>
                <dd className={route.metrics.no_travel_miles > 0 ? "danger" : ""}>
                  {route.metrics.no_travel_miles.toFixed(0)} mi
                </dd>
              </div>
              <div>
                <dt>Avg risk</dt>
                <dd>{route.metrics.avg_risk.toFixed(2)}</dd>
              </div>
            </dl>
          </button>
        );
      })}
    </div>
  );
}
