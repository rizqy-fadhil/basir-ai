"use client";

import { timeAgo } from "@/lib/api";

interface SnapshotHeroProps {
  snapshotUrl?: string;
  updatedAt?: string;
}

export default function SnapshotHero({
  snapshotUrl,
  updatedAt,
}: SnapshotHeroProps) {
  const hasSnapshot = !!snapshotUrl;

  return (
    <section
      aria-label="Snapshot area workspace"
      className="viewfinder relative overflow-hidden rounded-sm bg-roast"
    >
      {/* Viewfinder corners */}
      <span className="vf-bl" aria-hidden="true" />
      <span className="vf-br" aria-hidden="true" />

      {/* Snapshot image or empty state */}
      <div className="relative aspect-[16/9] w-full sm:aspect-[21/9]">
        {hasSnapshot ? (
          <>
            <img
              src={snapshotUrl}
              alt="Snapshot terbaru area workspace cafe"
              className="h-full w-full object-cover"
              loading="eager"
            />
            {/* Gradient overlay for text readability */}
            <div
              className="absolute inset-0 bg-gradient-to-t from-ink/80 via-ink/20 to-transparent"
              aria-hidden="true"
            />
            {/* Scanline — runs once on mount */}
            <div className="scanline-overlay" aria-hidden="true" />
          </>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center">
            <div>
              <div
                className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-oat/10"
                aria-hidden="true"
              >
                <svg
                  className="h-6 w-6 text-oat/40"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316Z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0ZM18.75 10.5h.008v.008h-.008V10.5Z"
                  />
                </svg>
              </div>
              <p className="font-mono text-caption text-oat/60">
                Kamera area ini belum mengirim data.
                <br />
                Coba lagi sebentar.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Timestamp bar */}
      {updatedAt && (
        <div className="absolute bottom-0 left-0 right-0 px-4 py-2">
          <time
            dateTime={updatedAt}
            className="font-mono text-caption text-oat/70"
          >
            Update {timeAgo(updatedAt)}
          </time>
        </div>
      )}
    </section>
  );
}
