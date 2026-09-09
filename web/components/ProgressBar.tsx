export function ProgressBar({
  label,
  percent,
  colorClass = "bg-trace",
}: {
  label: string;
  percent: number;
  colorClass?: string;
}) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-sm text-ink">{label}</span>
        <span className="font-mono text-xs text-ink-muted">{clamped}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-panel-raised">
        <div
          className={`h-full rounded-full ${colorClass}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
