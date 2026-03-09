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

export function FiltersSidebar(props: FiltersSidebarProps) {
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
        <h3>Tags</h3>
        <div className="chips">
          {props.tags.map((tag) => {
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
  onChange: (value: number | undefined) => void;
}

function RangeInput({ label, value, min, max, step, onChange }: RangeInputProps) {
  return (
    <label className="range-input">
      <span>{label}: {value ?? "Any"}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value ?? min}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <button type="button" className="clear-button" onClick={() => onChange(undefined)}>
        Clear
      </button>
    </label>
  );
}
