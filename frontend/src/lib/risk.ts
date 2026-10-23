import type { RiskLevel } from "../types";

export interface LevelMeta {
  label: string;
  color: string;
  tint: string;
  short: string;
}

// Colours are ordered by severity and stay distinguishable for the most common
// colour-vision deficiencies (green -> amber -> orange -> red -> maroon).
export const LEVELS: Record<RiskLevel, LevelMeta> = {
  0: { label: "Low", color: "#2f9e63", tint: "rgba(47,158,99,0.18)", short: "LOW" },
  1: { label: "Moderate", color: "#d8a22a", tint: "rgba(216,162,42,0.18)", short: "MOD" },
  2: { label: "High", color: "#e0722a", tint: "rgba(224,114,42,0.20)", short: "HIGH" },
  3: { label: "Severe", color: "#e05252", tint: "rgba(224,82,82,0.20)", short: "SEV" },
  4: { label: "No Travel", color: "#8c2f43", tint: "rgba(140,47,67,0.30)", short: "NO GO" },
};

export const LEVEL_LIST: RiskLevel[] = [0, 1, 2, 3, 4];

export function levelColor(level: RiskLevel): string {
  return (LEVELS[level] ?? LEVELS[0]).color;
}

export function formatHours(hours: number): string {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return m === 60 ? `${h + 1} h 00 m` : `${h} h ${String(m).padStart(2, "0")} m`;
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
