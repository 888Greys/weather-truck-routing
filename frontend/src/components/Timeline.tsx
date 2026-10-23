import type { PlanResponse } from "../types";
import { formatClock, LEVEL_LIST, LEVELS } from "../lib/risk";

interface Props {
  plan: PlanResponse | null;
  hour: number;
  onHourChange: (hour: number) => void;
  playing: boolean;
  onTogglePlay: () => void;
  showHeat: boolean;
  onToggleHeat: (value: boolean) => void;
}

export function Timeline({ plan, hour, onHourChange, playing, onTogglePlay, showHeat, onToggleHeat }: Props) {
  const horizon = plan?.heatmap.horizon_hours ?? 48;
  const stamp = plan?.heatmap.hours?.[hour] ?? null;

  return (
    <footer className="timeline">
      <div className="timeline-head">
        <button
          type="button"
          className="play"
          onClick={onTogglePlay}
          disabled={!plan}
          aria-label={playing ? "Pause forecast playback" : "Play forecast"}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <div className="timeline-readout">
          <span className="timeline-title">
            Forecast at departure +{hour} h
          </span>
          <span className="timeline-stamp">
            {stamp ? formatClock(stamp) : "plan a route to scrub the forecast"}
          </span>
        </div>
        <label className="heat-toggle">
          <input type="checkbox" checked={showHeat} onChange={(event) => onToggleHeat(event.target.checked)} />
          Corridor heat
        </label>
      </div>

      <input
        className="timeline-range"
        type="range"
        min={0}
        max={horizon}
        step={1}
        value={hour}
        onChange={(event) => onHourChange(Number(event.target.value))}
        aria-label="Forecast hour offset from departure"
        aria-valuetext={`${hour} hours after departure`}
      />
      <div className="timeline-ticks" aria-hidden="true">
        {[0, 12, 24, 36, 48].map((tick) => (
          <span key={tick} style={{ left: `${(tick / horizon) * 100}%` }}>
            {tick}h
          </span>
        ))}
      </div>

      <ul className="legend">
        {LEVEL_LIST.map((level) => (
          <li key={level}>
            <span className="swatch" style={{ background: LEVELS[level].color }} />
            {LEVELS[level].label}
          </li>
        ))}
      </ul>
    </footer>
  );
}
