import { useEffect, useId, useRef, useState } from "react";
import { geocode } from "../api";
import type { GeocodeResult, LatLon } from "../types";

interface Props {
  label: string;
  placeholder: string;
  value: LatLon | null;
  onChange: (value: LatLon | null) => void;
  onQueryChange?: (query: string) => void;
}

/**
 * Text input with debounced Nominatim suggestions.
 * Falls back to free text: the parent resolves it on submit if nothing is picked.
 */
export function PlaceInput({ label, placeholder, value, onChange, onQueryChange }: Props) {
  const [query, setQuery] = useState(value?.label ?? "");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputId = useId();

  useEffect(() => {
    if (value?.label && value.label !== query) setQuery(value.label);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value?.label]);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 3 || trimmed === value?.label) {
      setResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setBusy(true);
      try {
        const found = await geocode(trimmed, controller.signal);
        setResults(found);
        setActive(0);
      } catch {
        setResults([]);
      } finally {
        setBusy(false);
      }
    }, 350);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [query, value?.label]);

  useEffect(() => {
    function onDocumentClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  function choose(result: GeocodeResult) {
    onChange({ lat: result.lat, lon: result.lon, label: result.label });
    setQuery(result.label);
    setOpen(false);
    onQueryChange?.(result.label);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (index + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (index - 1 + results.length) % results.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(results[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="field place-field" ref={containerRef}>
      <label htmlFor={inputId}>{label}</label>
      <div className="place-input">
        <input
          id={inputId}
          type="text"
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            if (value) onChange(null);
            onQueryChange?.(event.target.value);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          aria-autocomplete="list"
          aria-expanded={open && results.length > 0}
        />
        {busy && <span className="spinner" aria-label="Searching" />}
        {value && <span className="place-pin" aria-hidden="true">✓</span>}
      </div>
      {open && results.length > 0 && (
        <ul className="suggestions" role="listbox">
          {results.map((result, index) => (
            <li key={`${result.lat},${result.lon},${index}`}>
              <button
                type="button"
                className={index === active ? "active" : undefined}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(result)}
                role="option"
                aria-selected={index === active}
              >
                <strong>{result.name}</strong>
                <span>{result.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
