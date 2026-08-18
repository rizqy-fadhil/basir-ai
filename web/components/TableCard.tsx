"use client";

import { type Meja, statusLabel, statusColor } from "@/lib/api";

interface TableCardProps {
  meja: Meja;
}

const colorMap = {
  scan: {
    vf: "#4FBEB0",
    badge: "bg-scan/15 text-scan",
    focusRing: "focus-visible:outline-scan",
  },
  amber: {
    vf: "#E3A93F",
    badge: "bg-amber/15 text-amber",
    focusRing: "focus-visible:outline-amber",
  },
  ember: {
    vf: "#D2622E",
    badge: "bg-ember/15 text-ember",
    focusRing: "focus-visible:outline-ember",
  },
} as const;

export default function TableCard({ meja }: TableCardProps) {
  const color = statusColor(meja.status);
  const label = statusLabel(meja.status);
  const { vf, badge, focusRing } = colorMap[color];

  const paddedNumber = String(meja.nomor_meja).padStart(2, "0");

  return (
    <article
      className={`viewfinder viewfinder-interactive relative rounded-sm bg-roast p-4 transition-colors ${focusRing}`}
      style={{ "--vf-color": vf } as React.CSSProperties}
      tabIndex={0}
      role="region"
      aria-label={`Meja ${paddedNumber}: ${label}, ${meja.terisi} dari ${meja.kapasitas} terisi`}
    >
      {/* Viewfinder bottom corners */}
      <span className="vf-bl" aria-hidden="true" />
      <span className="vf-br" aria-hidden="true" />

      {/* Table number */}
      <h3 className="font-mono text-table-title uppercase tracking-wider text-oat/90">
        Meja {paddedNumber}
      </h3>

      {/* Occupancy fraction */}
      <p className="mt-2 font-mono text-3xl font-bold tabular-nums text-oat">
        {meja.terisi}
        <span className="text-lg text-oat/40">/{meja.kapasitas}</span>
      </p>

      {/* Status badge */}
      <span
        className={`mt-3 inline-block rounded-sm px-2.5 py-1 font-mono text-caption font-bold uppercase tracking-wide ${badge}`}
      >
        {label}
      </span>
    </article>
  );
}
