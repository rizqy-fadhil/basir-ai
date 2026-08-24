// ─── Types (sesuai ARCHITECTURE.md section 8 API contract) ───

export type MejaStatus = "available" | "partial" | "occupied" | null;

export interface Meja {
  nomor_meja: number;
  kapasitas: number;
  terisi: number;
  status: MejaStatus;  // null when AI inference hasn't run yet
}

export interface CafeStatus {
  cafe_id: number;
  okupansi_persen: number | null;
  updated_at: string | null;
  snapshot_url?: string;
  meja: Meja[];
}

// ─── SWR fetcher ─────────────────────────────────────────────

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const error = new Error(`API error: ${res.status} ${res.statusText}`);
    (error as any).status = res.status;
    throw error;
  }
  return res.json() as Promise<T>;
}

// ─── Polling interval (45s sesuai DETECTION_INTERVAL_SECONDS) ─

export const POLLING_INTERVAL_MS = 45_000;

// ─── Status helpers ──────────────────────────────────────────

/** Map API status ke label bahasa Indonesia (DESIGN.md section 5) */
export function statusLabel(status: MejaStatus): string {
  switch (status) {
    case "available":
      return "Tersedia";
    case "partial":
      return "Sebagian Terisi";
    case "occupied":
      return "Penuh";
    default:
      return "Belum ada data";
  }
}

/** Map API status ke Tailwind color key */
export type StatusColorKey = "scan" | "amber" | "ember" | "neutral";

export function statusColor(status: MejaStatus): StatusColorKey {
  switch (status) {
    case "available":
      return "scan";
    case "partial":
      return "amber";
    case "occupied":
      return "ember";
    default:
      return "neutral";
  }
}

// ─── Time helpers ────────────────────────────────────────────

/** Format timestamp ke "X menit lalu" */
export function timeAgo(isoString: string | null | undefined): string {
  if (!isoString) return "Menunggu data";

  const diff = Date.now() - new Date(isoString).getTime();
  const seconds = Math.floor(diff / 1000);

  if (seconds < 60) return "Baru saja";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  return "Lebih dari sehari lalu";
}
