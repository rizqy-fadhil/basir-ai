export default function EmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-sm border border-ember/20 bg-roast px-6 py-12 text-center"
      role="status"
      aria-live="polite"
    >
      {/* Icon: clock */}
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
            d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
          />
        </svg>
      </div>

      <p className="font-mono text-table-title text-oat">
        Semua meja penuh saat ini.
      </p>
      <p className="mt-1 text-sm text-oat/60">
        Coba cek lagi dalam beberapa menit.
      </p>
    </div>
  );
}
