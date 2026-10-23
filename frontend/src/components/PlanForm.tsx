import { useEffect, useState } from "react";
import type { LatLon, PlanRequest } from "../types";
import { formatDateTime } from "../lib/risk";
import { PlaceInput } from "./PlaceInput";

interface Props {
  loading: boolean;
  hasPlan: boolean;
  onPlan: (request: PlanRequest) => void;
}

interface Preset {
  label: string;
  origin: LatLon;
  destination: LatLon;
  weight: number;
}

const PRESETS: Preset[] = [
  {
    label: "Nairobi → Mombasa",
    origin: { lat: -1.2921, lon: 36.8219, label: "Nairobi, Kenya" },
    destination: { lat: -4.0435, lon: 39.6682, label: "Mombasa, Kenya" },
    weight: 38000,
  },
  {
    label: "Denver → Salt Lake",
    origin: { lat: 39.7392, lon: -104.9903, label: "Denver, Colorado" },
    destination: { lat: 40.7608, lon: -111.891, label: "Salt Lake City, Utah" },
    weight: 42000,
  },
  {
    label: "Chicago → Denver",
    origin: { lat: 41.8781, lon: -87.6298, label: "Chicago, Illinois" },
    destination: { lat: 39.7392, lon: -104.9903, label: "Denver, Colorado" },
    weight: 68000,
  },
];

function defaultDeparture(): string {
  const date = new Date(Date.now() + 4 * 3600 * 1000);
  date.setMinutes(0, 0, 0);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function PlanForm({ loading, hasPlan, onPlan }: Props) {
  const [origin, setOrigin] = useState<LatLon | null>(PRESETS[0].origin);
  const [destination, setDestination] = useState<LatLon | null>(PRESETS[0].destination);
  const [departure, setDeparture] = useState(defaultDeparture());
  const [weight, setWeight] = useState(PRESETS[0].weight);
  const [spacing, setSpacing] = useState(25);
  const [scenario, setScenario] = useState<"live" | "stress">("live");
  const [formError, setFormError] = useState<string | null>(null);
  const [editing, setEditing] = useState(true);

  // Collapse to a summary once a plan exists, so the route list has room.
  useEffect(() => {
    if (hasPlan) setEditing(false);
  }, [hasPlan]);

  function applyPreset(preset: Preset) {
    setOrigin(preset.origin);
    setDestination(preset.destination);
    setWeight(preset.weight);
    setFormError(null);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!origin || !destination) {
      setFormError("Pick both an origin and a destination from the suggestions.");
      return;
    }
    if (!departure) {
      setFormError("Choose a departure date and time.");
      return;
    }
    setFormError(null);
    setEditing(false);
    onPlan({
      origin,
      destination,
      depart_at: new Date(departure).toISOString(),
      weight_lb: weight,
      sample_interval_miles: spacing,
      horizon_hours: 48,
      scenario,
    });
  }

  if (hasPlan && !editing) {
    return (
      <div className="trip-summary">
        <div className="trip-route">
          <span className="trip-point">{origin?.label ?? "—"}</span>
          <span className="trip-arrow" aria-hidden="true">→</span>
          <span className="trip-point">{destination?.label ?? "—"}</span>
        </div>
        <div className="trip-meta">
          <span>{formatDateTime(new Date(departure).toISOString())}</span>
          <span>{weight.toLocaleString()} lb</span>
          <span>every {spacing} mi</span>
          <span className={scenario === "stress" ? "warn" : undefined}>
            {scenario === "stress" ? "storm demo" : "live forecast"}
          </span>
        </div>
        <button type="button" className="ghost" onClick={() => setEditing(true)}>
          Edit trip
        </button>
      </div>
    );
  }

  return (
    <form className="plan-form" onSubmit={submit}>
      <div className="presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="preset"
            onClick={() => applyPreset(preset)}
            title={preset.label}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <PlaceInput label="Origin" placeholder="City or address" value={origin} onChange={setOrigin} />
      <PlaceInput
        label="Destination"
        placeholder="City or address"
        value={destination}
        onChange={setDestination}
      />

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="spacing">Checkpoints</label>
          <select id="spacing" value={spacing} onChange={(event) => setSpacing(Number(event.target.value))}>
            <option value={10}>Every 10 mi</option>
            <option value={25}>Every 25 mi</option>
            <option value={50}>Every 50 mi</option>
          </select>
        </div>
      </div>

      <div className="field">
        <label htmlFor="weight">
          Load weight <span className="value">{weight.toLocaleString()} lb</span>
        </label>
        <input
          id="weight"
          type="range"
          min={0}
          max={80000}
          step={1000}
          value={weight}
          onChange={(event) => setWeight(Number(event.target.value))}
          aria-valuetext={`${weight.toLocaleString()} pounds`}
        />
        <div className="field-hint">
          Above 30,000 lb, 45–54 mph becomes <strong>No Travel</strong>; above 40,000 lb, 35–44 mph
          becomes <strong>Severe</strong>.
        </div>
      </div>

      <div className="field">
        <span className="label-text">Weather source</span>
        <div className="segmented" role="radiogroup" aria-label="Weather source">
          <button
            type="button"
            role="radio"
            aria-checked={scenario === "live"}
            className={scenario === "live" ? "active" : undefined}
            onClick={() => setScenario("live")}
          >
            Live forecast
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={scenario === "stress"}
            className={scenario === "stress" ? "active" : undefined}
            onClick={() => setScenario("stress")}
          >
            Storm demo
          </button>
        </div>
        {scenario === "stress" && (
          <div className="field-hint warn">
            Simulated weather system, not a real forecast. Used to exercise the Severe and No Travel
            rules.
          </div>
        )}
      </div>

      {formError && <p className="form-error" role="alert">{formError}</p>}

      <div className="form-actions">
        <button type="submit" className="primary" disabled={loading}>
          {loading ? "Planning…" : "Plan safest route"}
        </button>
        {hasPlan && (
          <button type="button" className="ghost" onClick={() => setEditing(false)}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
