import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, fetchPlan } from "./api";
import type { PlanRequest, PlanResponse } from "./types";
import { PlanForm } from "./components/PlanForm";
import { RouteList } from "./components/RouteList";
import { RouteMap } from "./components/RouteMap";
import { Timeline } from "./components/Timeline";
import { formatDateTime, formatHours } from "./lib/risk";

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hour, setHour] = useState(0);
  const [showHeat, setShowHeat] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const runPlan = useCallback(async (request: PlanRequest) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    setPlaying(false);
    try {
      const result = await fetchPlan(request, controller.signal);
      setPlan(result);
      setSelectedId(result.recommendation.route_id);
      setHour(0);
    } catch (caught) {
      if ((caught as Error).name === "AbortError") return;
      const message =
        caught instanceof ApiError ? caught.message : "Could not reach the planning API. Is the backend running?";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!playing || !plan) return;
    const horizon = plan.heatmap.horizon_hours;
    const timer = window.setInterval(() => {
      setHour((current) => (current + 1) % (horizon + 1));
    }, 550);
    return () => window.clearInterval(timer);
  }, [playing, plan]);

  const selected = plan?.routes.find((route) => route.id === selectedId) ?? null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">◈</span>
          <div>
            <h1>Weather-Aware Truck Routing</h1>
            <p>Route risk from hourly forecast, load weight and drive time</p>
          </div>
        </div>
        <div className="topbar-meta">
          {plan && (
            <>
              <span className={`pill${plan.request.scenario === "stress" ? " pill-warn" : ""}`}>
                {plan.request.scenario === "stress" ? "Storm demo (simulated)" : "Live forecast"}
              </span>
              <span className="pill pill-quiet">
                {plan.meta.weather_provider} · {plan.meta.routing_provider}
              </span>
              <span className="pill pill-quiet">{plan.request.weight_lb.toLocaleString()} lb</span>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <strong>Planning failed.</strong> {error}
          <button type="button" onClick={() => setError(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      <div className="workspace">
        <aside className="sidebar">
          <section className="panel">
            <h2 className="panel-title">Trip</h2>
            <PlanForm loading={loading} hasPlan={!!plan} onPlan={runPlan} />
          </section>

          {plan && (
            <section className="panel">
              <h2 className="panel-title">
                Routes
                <span className="panel-sub">
                  {formatDateTime(plan.request.depart_at)} · every {plan.request.sample_interval_miles} mi
                </span>
              </h2>
              <div className="recommendation">
                <div className="recommendation-head">
                  <span className="badge">Recommended</span>
                  <strong>{plan.recommendation.label}</strong>
                </div>
                <ul>
                  {plan.recommendation.rationale.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>
              <RouteList routes={plan.routes} selectedId={selectedId} onSelect={setSelectedId} />
            </section>
          )}
        </aside>

        <main className="map-area">
          <RouteMap plan={plan} selectedId={selectedId} hour={hour} showHeat={showHeat} />

          {!plan && !loading && (
            <div className="map-empty">
              <h2>Plan a trip to see the corridor</h2>
              <p>
                Three road routes are scored mile by mile against the hourly forecast at each
                checkpoint, using the load-aware wind, rain and snow thresholds.
              </p>
            </div>
          )}

          {loading && (
            <div className="map-loading" role="status">
              <span className="spinner large" />
              Fetching routes, sampling weather every {plan ? plan.request.sample_interval_miles : 25} miles…
            </div>
          )}

          {selected && (
            <div className="map-overlay">
              <div className="overlay-head">
                <strong>{selected.label}</strong>
                <span>{formatHours(selected.duration_hours)} · {selected.distance_miles.toFixed(0)} mi</span>
              </div>
              <p>{selected.summary}</p>
            </div>
          )}
        </main>
      </div>

      <Timeline
        plan={plan}
        hour={hour}
        onHourChange={(value) => {
          setPlaying(false);
          setHour(value);
        }}
        playing={playing}
        onTogglePlay={() => setPlaying((value) => !value)}
        showHeat={showHeat}
        onToggleHeat={setShowHeat}
      />
    </div>
  );
}
