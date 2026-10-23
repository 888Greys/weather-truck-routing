import type { GeocodeResult, PlanRequest, PlanResponse } from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail) {
      const first = Object.values(body.detail)[0];
      if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    }
    if (typeof body?.error === "string") return body.error;
  } catch {
    /* fall through to a generic message */
  }
  return `Request failed (${response.status})`;
}

export async function fetchPlan(input: PlanRequest, signal?: AbortSignal): Promise<PlanResponse> {
  const response = await fetch(`${BASE}/api/plan/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    signal,
  });
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return (await response.json()) as PlanResponse;
}

export async function geocode(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
  const response = await fetch(`${BASE}/api/geocode/?q=${encodeURIComponent(query)}`, { signal });
  if (!response.ok) return [];
  const body = (await response.json()) as { results: GeocodeResult[] };
  return body.results ?? [];
}
