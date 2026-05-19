import { ALL_RANGES, type RangeLabel } from "../types";

interface Props {
  value: RangeLabel;
  onChange: (r: RangeLabel) => void;
}

export function TimeframeBar({ value, onChange }: Props) {
  return (
    <div className="timeframe-bar">
      {ALL_RANGES.map((r) => (
        <button
          key={r}
          className={`tf ${value === r ? "active" : ""}`}
          onClick={() => onChange(r)}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
