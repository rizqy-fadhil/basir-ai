"use client";

import useSWR from "swr";
import {
  type CafeStatus,
  fetcher,
  POLLING_INTERVAL_MS,
} from "@/lib/api";
import SnapshotHero from "@/components/SnapshotHero";
import OccupancyBar from "@/components/OccupancyBar";
import TableCard from "@/components/TableCard";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PrivacyFooter from "@/components/PrivacyFooter";

interface PageProps {
  params: { id: string };
}

export default function CafeDashboard({ params }: PageProps) {
  const { id } = params;

  const { data, error, isLoading, mutate } = useSWR<CafeStatus>(
    `/cafes/${id}/status`,
    fetcher,
    {
      refreshInterval: POLLING_INTERVAL_MS,
      revalidateOnFocus: true,
      errorRetryCount: 3,
      errorRetryInterval: 5000,
    }
  );

  // ── Loading skeleton ─────────────────────────────────
  if (isLoading) {
    return (
      <div className="mx-auto min-h-dvh max-w-2xl px-4 py-6">
        <Header />
        {/* Skeleton hero */}
        <div className="mb-6 aspect-[16/9] animate-pulse rounded-sm bg-roast sm:aspect-[21/9]" />
        {/* Skeleton bar */}
        <div className="mb-8 space-y-3">
          <div className="h-4 w-32 animate-pulse rounded bg-roast" />
          <div className="h-16 w-40 animate-pulse rounded bg-roast" />
          <div className="h-2.5 w-full animate-pulse rounded-full bg-roast" />
        </div>
        {/* Skeleton cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-sm bg-roast"
            />
          ))}
        </div>
      </div>
    );
  }

  // ── Error state ──────────────────────────────────────
  if (error) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 py-6">
        <Header />
        <div className="flex flex-1 items-center justify-center">
          <ErrorState
            message={
              (error as any).status === 404
                ? "Cafe tidak ditemukan. Periksa URL Anda."
                : undefined
            }
            onRetry={() => mutate()}
          />
        </div>
        <PrivacyFooter />
      </div>
    );
  }

  // ── Data loaded ──────────────────────────────────────
  const allOccupied =
    data!.meja.length > 0 &&
    data!.meja.every((m) => m.status === "occupied");

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 py-6">
      <Header />

      <main className="flex-1 space-y-6">
        {/* Hero snapshot */}
        <SnapshotHero
          snapshotUrl={data!.snapshot_url}
          updatedAt={data!.updated_at ?? undefined}
        />

        {/* Occupancy bar */}
        <OccupancyBar percentage={data!.okupansi_persen} />

        {/* Table grid or empty state */}
        {allOccupied ? (
          <EmptyState />
        ) : (
          <section aria-label="Daftar meja">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {data!.meja.map((meja) => (
                <TableCard key={meja.nomor_meja} meja={meja} />
              ))}
            </div>
          </section>
        )}
      </main>

      <PrivacyFooter />
    </div>
  );
}

/** Sticky-ish header with title */
function Header() {
  return (
    <header className="mb-6">
      <p className="font-mono text-caption uppercase tracking-widest text-scan">
        Basir AI
      </p>
      <h1 className="mt-1 font-sans text-xl font-medium text-oat text-balance sm:text-2xl">
        Cek dulu sebelum berangkat
      </h1>
    </header>
  );
}
