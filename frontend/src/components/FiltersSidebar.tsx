import { useMemo, useState } from "react";

interface FiltersSidebarProps {
  tags: string[];
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

const DEFAULT_VISIBLE_TAG_COUNT = 18;

export function FiltersSidebar(props: FiltersSidebarProps) {
  const [showAllTags, setShowAllTags] = useState(false);
  const orderedTags = useMemo(() => {
    const uniqueTags = Array.from(new Set(props.tags));
    const selected = uniqueTags
      .filter((tag) => props.selectedTags.includes(tag))
      .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    const unselected = uniqueTags
      .filter((tag) => !props.selectedTags.includes(tag))
      .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));

    return [...selected, ...unselected];
  }, [props.selectedTags, props.tags]);

  const visibleTags = showAllTags ? orderedTags : orderedTags.slice(0, DEFAULT_VISIBLE_TAG_COUNT);
  const hiddenTagsCount = Math.max(0, orderedTags.length - visibleTags.length);

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
        <div className="chips tag-grid">
          {visibleTags.map((tag) => {
            const selected = props.selectedTags.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                className={selected ? "chip selected" : "chip"}
                onClick={() => props.onToggleTag(tag)}
              >
                {tag}
              </button>
            );
          })}
        </div>
        {hiddenTagsCount > 0 ? (
          <button
            type="button"
            className="tag-list-toggle"
            onClick={() => setShowAllTags((prev) => !prev)}
          >
            {showAllTags ? "Show fewer tags" : `Show ${hiddenTagsCount} more tags`}
          </button>
        ) : null}
      </div>
    </aside>
  );
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
        Range: {min} to {max}{unit ? ` ${unit}` : ""}
      </small>
    </label>
  );
}
