import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { PlanResponse, RiskLevel, RouteOption } from "../types";
import { formatClock, formatHours, levelColor, LEVELS } from "../lib/risk";
import { HeatLayer } from "./HeatLayer";

interface Props {
  plan: PlanResponse | null;
  selectedId: string | null;
  hour: number;
  showHeat: boolean;
}

function HeatOverlay({ cells, hour, visible }: { cells: { lat: number; lon: number; miles: number; levels: RiskLevel[] }[]; hour: number; visible: boolean }) {
  const map = useMap();
  const layerRef = useRef<HeatLayer | null>(null);

  useEffect(() => {
    const layer = new HeatLayer();
    layer.addTo(map);
    layerRef.current = layer;
    return () => {
      layer.remove();
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    layerRef.current?.setCells(cells);
  }, [cells]);

  useEffect(() => {
    layerRef.current?.setHour(hour);
  }, [hour]);

  useEffect(() => {
    layerRef.current?.setVisible(visible);
  }, [visible]);

  return null;
}

function FitToRoutes({ plan }: { plan: PlanResponse | null }) {
  const map = useMap();
  useEffect(() => {
    if (!plan) return;
    const points = plan.routes.flatMap((route) => route.geometry);
    if (points.length === 0) return;
    const bounds = L.latLngBounds(points.map(([lat, lon]) => L.latLng(lat, lon)));
    map.fitBounds(bounds, { padding: [48, 48], animate: true });
  }, [map, plan]);
  return null;
}

export function RouteMap({ plan, selectedId, hour, showHeat }: Props) {
  const selected = useMemo(
    () => plan?.routes.find((route) => route.id === selectedId) ?? null,
    [plan, selectedId],
  );
  const cells = selectedId ? plan?.heatmap.routes[selectedId]?.cells ?? [] : [];

  const centre: [number, number] = selected
    ? [selected.geometry[Math.floor(selected.geometry.length / 2)][0], selected.geometry[Math.floor(selected.geometry.length / 2)][1]]
    : [-1.29, 36.82];

  return (
    <MapContainer center={centre} zoom={7} className="map" zoomControl={false} preferCanvas>
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />
      <FitToRoutes plan={plan} />

      {plan?.routes.map((route) => (
        <Polyline
          key={route.id}
          positions={route.geometry}
          pathOptions={{
            color: route.id === selectedId ? "#f0f6fc" : "#8b949e",
            weight: route.id === selectedId ? 5 : 3,
            opacity: route.id === selectedId ? 0.95 : 0.45,
            lineCap: "round",
          }}
          eventHandlers={{}}
        />
      ))}

      {selected && (
        <HeatOverlay cells={cells} hour={hour} visible={showHeat} />
      )}

      {selected?.checkpoints.map((checkpoint, index) => (
        <CircleMarker
          key={`${selected.id}-${index}`}
          center={[checkpoint.lat, checkpoint.lon]}
          radius={6}
          pathOptions={{
            color: "#0d1117",
            weight: 2,
            fillColor: levelColor(checkpoint.level),
            fillOpacity: 0.95,
          }}
        >
          <Tooltip direction="top" offset={[0, -8]} opacity={1}>
            <div className="cp-tooltip">
              <strong>Mile {checkpoint.miles.toFixed(0)}</strong>
              <span>{LEVELS[checkpoint.level].label}</span>
            </div>
          </Tooltip>
          <Popup>
            <div className="cp-popup">
              <header>
                <span className="dot" style={{ background: levelColor(checkpoint.level) }} />
                <strong>{checkpoint.level_label}</strong>
                <span className="muted">mile {checkpoint.miles.toFixed(0)}</span>
              </header>
              <p className="muted">ETA {formatClock(checkpoint.eta)}</p>
              <ul>
                <li>Wind <strong>{checkpoint.wind_mph.toFixed(0)} mph</strong></li>
                <li>Rain <strong>{checkpoint.rain_in_hr.toFixed(2)} in/hr</strong></li>
                {checkpoint.snow_in_hr > 0 && <li>Snow <strong>{checkpoint.snow_in_hr.toFixed(2)} in/hr</strong></li>}
                <li>Temp <strong>{checkpoint.temp_c.toFixed(0)} °C</strong></li>
              </ul>
              {checkpoint.reasons.map((reason) => (
                <p className="reason" key={reason}>{reason}</p>
              ))}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

export function RouteSummaryStrip({ route }: { route: RouteOption }) {
  return (
    <div className="strip">
      <span>{route.label}</span>
      <span>{formatHours(route.duration_hours)}</span>
      <span>{route.distance_miles.toFixed(0)} mi</span>
    </div>
  );
}
