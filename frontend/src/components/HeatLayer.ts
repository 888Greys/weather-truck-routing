import L from "leaflet";
import type { HeatCell, RiskLevel } from "../types";
import { levelColor } from "../lib/risk";

/**
 * Canvas overlay that paints corridor heat cells as soft risk blobs.
 *
 * Drawn imperatively rather than as React markers: the layer is redrawn on every
 * pan frame and on every slider tick, and a 3-route corridor is ~60 cells -
 * hundreds of DOM nodes would stutter, a handful of gradients will not.
 */
export class HeatLayer extends L.Layer {
  private canvas: HTMLCanvasElement | null = null;
  private cells: HeatCell[] = [];
  private hour = 0;
  private visible = true;
  private frame = 0;

  constructor(cells: HeatCell[] = []) {
    super();
    this.cells = cells;
  }

  onAdd(map: L.Map): this {
    if (!map.getPane("heatPane")) {
      const pane = map.createPane("heatPane");
      pane.style.zIndex = "380";
      pane.style.pointerEvents = "none";
    }
    const canvas = L.DomUtil.create("canvas", "heat-canvas") as HTMLCanvasElement;
    canvas.style.position = "absolute";
    canvas.style.pointerEvents = "none";
    map.getPane("heatPane")!.appendChild(canvas);
    this.canvas = canvas;
    map.on("move zoom resize viewreset", this.schedule, this);
    this.schedule();
    return this;
  }

  onRemove(map: L.Map): this {
    map.off("move zoom resize viewreset", this.schedule, this);
    this.canvas?.remove();
    this.canvas = null;
    if (this.frame) cancelAnimationFrame(this.frame);
    return this;
  }

  setCells(cells: HeatCell[]): void {
    this.cells = cells;
    this.schedule();
  }

  setHour(hour: number): void {
    if (hour === this.hour) return;
    this.hour = hour;
    this.schedule();
  }

  setVisible(visible: boolean): void {
    if (visible === this.visible) return;
    this.visible = visible;
    this.schedule();
  }

  private schedule(): void {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.redraw();
    });
  }

  private redraw(): void {
    const map = (this as unknown as { _map?: L.Map })._map;
    const canvas = this.canvas;
    if (!map || !canvas) return;

    const size = map.getSize();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]));
    if (canvas.width !== size.x * dpr || canvas.height !== size.y * dpr) {
      canvas.width = size.x * dpr;
      canvas.height = size.y * dpr;
      canvas.style.width = `${size.x}px`;
      canvas.style.height = `${size.y}px`;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);
    if (!this.visible || this.cells.length === 0) return;

    // Convert the cell spacing (miles) into screen pixels for the current zoom,
    // so blobs always cover the stretch of road they describe.
    const centre = map.getCenter();
    const probe = L.latLng(centre.lat + 0.5, centre.lng);
    const pixelsPerDegree = Math.abs(
      map.latLngToContainerPoint(probe).y - map.latLngToContainerPoint(centre).y,
    ) / 0.5;
    const radius = Math.max(8, (12.5 / 69.05) * pixelsPerDegree * 1.15);

    for (const cell of this.cells) {
      const level = (cell.levels[this.hour] ?? cell.levels[0] ?? 0) as RiskLevel;
      const point = map.latLngToContainerPoint([cell.lat, cell.lon]);
      if (point.x < -radius * 2 || point.y < -radius * 2 || point.x > size.x + radius * 2 || point.y > size.y + radius * 2) {
        continue;
      }
      const colour = levelColor(level);
      const gradient = ctx.createRadialGradient(point.x, point.y, radius * 0.15, point.x, point.y, radius);
      gradient.addColorStop(0, hexToRgba(colour, 0.46));
      gradient.addColorStop(0.65, hexToRgba(colour, 0.26));
      gradient.addColorStop(1, hexToRgba(colour, 0));
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const bigint = parseInt(value, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}
