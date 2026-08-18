"use client";

interface OccupancyBarProps {
  /** Percentage 0–100 */
  percentage: number;
}

export default function OccupancyBar({ percentage }: OccupancyBarProps) {
  const clamped = Math.max(0, Math.min(100, percentage));

  // Color tier per DESIGN.md
  let barColor: string;
  let barBg: string;
  if (clamped < 50) {
    barColor = "bg-scan";
    barBg = "bg-scan/20";
  } else if (clamped <= 80) {
    barColor = "bg-amber";
    barBg = "bg-amber/20";
  } else {
    barColor = "bg-ember";
    barBg = "bg-ember/20";
  }

  return (
    <div className="space-y-2" role="group" aria-label="Okupansi cafe">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-sans text-oat/80 uppercase tracking-wide">
          Okupansi cafe
        </span>
        <span className="font-mono text-hero-number tabular-nums text-oat">
          {clamped}
          <span className="text-2xl text-oat/60">%</span>
        </span>
      </div>

      {/* Progress bar */}
      <div
        className={`h-2.5 w-full overflow-hidden rounded-full ${barBg}`}
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Okupansi cafe: ${clamped}%`}
      >
        <div
          className={`h-full rounded-full ${barColor} animate-fill-bar`}
          style={
            { "--fill-width": `${clamped}%`, width: `${clamped}%` } as React.CSSProperties
          }
        />
      </div>
    </div>
  );
}
