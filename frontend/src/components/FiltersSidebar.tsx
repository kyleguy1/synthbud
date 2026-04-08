import { useMemo } from "react";

import type { TagFacet } from "../types";

interface FiltersSidebarProps {
  tagFacets: TagFacet[];
  selectedTags: string[];
  minDuration?: number;
  maxDuration?: number;
  minBrightness?: number;
  maxBrightness?: number;
  bpmMin?: number;
  bpmMax?: number;
  onToggleTag: (tag: string) => void;
  onRangeChange: (key: RangeKey, value: number | undefined) => void;
}

type RangeKey =
  | "minDuration"
  | "maxDuration"
  | "minBrightness"
  | "maxBrightness"
  | "bpmMin"
  | "bpmMax";

const SPECIAL_TAG_LABELS: Record<string, string> = {
  "drum-and-bass": "Drum & Bass",
  "hip-hop": "Hip-Hop",
  "lo-fi": "Lo-Fi",
  "one-shot": "One-Shot"
};

export function FiltersSidebar(props: FiltersSidebarProps) {
  const orderedFacets = useMemo(
    () =>
      props.tagFacets
        .map((facet) => {
          const uniqueTags = Array.from(new Set(facet.tags));
          const selected = uniqueTags.filter((tag) => props.selectedTags.includes(tag));
          const unselected = uniqueTags.filter((tag) => !props.selectedTags.includes(tag));
          return {
            ...facet,
            tags: [...selected, ...unselected]
          };
        })
        .filter((facet) => facet.tags.length > 0),
    [props.selectedTags, props.tagFacets]
  );

  return (
    <aside className="filters-sidebar">
      <h2>Filters</h2>
      <div className="filter-block">
        <h3>Duration (sec)</h3>
        <RangeInput
          label="Min"
          value={props.minDuration}
          min={0}
          max={30}
          step={1}
          onChange={(value) => props.onRangeChange("minDuration", value)}
        />
        <RangeInput
          label="Max"
          value={props.maxDuration}
          min={0}
          max={30}
          step={1}
          onChange={(value) => props.onRangeChange("maxDuration", value)}
        />
      </div>

      <div className="filter-block">
        <h3>Brightness</h3>
        <RangeInput
          label="Min"
          value={props.minBrightness}
          min={0}
          max={12000}
          step={100}
          onChange={(value) => props.onRangeChange("minBrightness", value)}
        />
        <RangeInput
          label="Max"
          value={props.maxBrightness}
          min={0}
          max={12000}
          step={100}
          onChange={(value) => props.onRangeChange("maxBrightness", value)}
        />
      </div>

      <div className="filter-block">
        <h3>BPM</h3>
        <RangeInput
          label="Min"
          value={props.bpmMin}
          min={40}
          max={220}
          step={1}
          onChange={(value) => props.onRangeChange("bpmMin", value)}
        />
        <RangeInput
          label="Max"
          value={props.bpmMax}
          min={40}
          max={220}
          step={1}
          onChange={(value) => props.onRangeChange("bpmMax", value)}
        />
      </div>

      <div className="filter-block">
        <div className="filter-heading">
          <h3>Tags</h3>
          <span>{props.selectedTags.length} selected</span>
        </div>
        <div className="tag-facet-stack">
          {orderedFacets.map((facet) => (
            <section key={facet.key} className="tag-facet-group" aria-label={facet.label}>
              <h4>{facet.label}</h4>
              <div className="chips tag-grid">
                {facet.tags.map((tag) => {
                  const selected = props.selectedTags.includes(tag);
                  return (
                    <button
                      key={tag}
                      type="button"
                      className={selected ? "chip selected" : "chip"}
                      onClick={() => props.onToggleTag(tag)}
                    >
                      {formatTagLabel(tag)}
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
    </aside>
  );
}

function formatTagLabel(tag: string): string {
  const special = SPECIAL_TAG_LABELS[tag];
  if (special) {
    return special;
  }
  return tag
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

interface RangeInputProps {
  label: string;
  value: number | undefined;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number | undefined) => void;
}

function RangeInput({ label, value, min, max, step, unit, onChange }: RangeInputProps) {
  return (
    <label className="range-input">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value ?? ""}
        placeholder={`Any${unit ? ` ${unit}` : ""}`}
        inputMode="decimal"
        onChange={(event) => {
          const nextValue = event.target.value.trim();
          onChange(nextValue === "" ? undefined : Number(nextValue));
        }}
      />
      <small>
        Range: {min} to {max}
        {unit ? ` ${unit}` : ""}
      </small>
    </label>
  );
}
