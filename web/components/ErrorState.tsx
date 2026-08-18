"use client";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-sm border border-ember/30 bg-roast px-6 py-12 text-center"
      role="alert"
    >
      {/* Icon: exclamation triangle */}
      <div
        className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-ember/10"
        aria-hidden="true"
      >
        <svg
          className="h-7 w-7 text-ember"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
      </div>

      <p className="font-mono text-table-title text-oat">
        Gagal memuat data
      </p>
      <p className="mt-1 max-w-xs text-sm text-oat/60">
        {message ?? "Terjadi kesalahan saat mengambil data cafe. Periksa koneksi internet Anda."}
      </p>

      {onRetry && (
        <button
          onClick={onRetry}
          className="viewfinder viewfinder-interactive mt-6 rounded-sm bg-roast px-5 py-2.5 font-mono text-caption font-bold uppercase tracking-wider text-scan transition-colors hover:bg-scan/10 focus-visible:outline-scan"
          style={{ "--vf-color": "#4FBEB0" } as React.CSSProperties}
        >
          <span className="vf-bl" aria-hidden="true" />
          <span className="vf-br" aria-hidden="true" />
          Coba lagi
        </button>
      )}
    </div>
  );
}
