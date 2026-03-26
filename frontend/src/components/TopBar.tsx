interface TopBarProps {
  query: string;
  cc0Only: boolean;
  onQueryChange: (value: string) => void;
  onToggleCc0: (value: boolean) => void;
}

export function TopBar({ query, cc0Only, onQueryChange, onToggleCc0 }: TopBarProps) {
  return (
    <div className="top-bar">
      <input
        type="search"
        placeholder="Search sounds, tags, creators"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        aria-label="Search sounds"
      />
      <label className="toggle">
        <input
          type="checkbox"
          checked={cc0Only}
          onChange={(event) => onToggleCc0(event.target.checked)}
        />
        CC0 only
      </label>
    </div>
  );
}
