import { useEffect, useState } from 'react'

export function Footer() {
  const [syncedAt, setSyncedAt] = useState(() => new Date())

  useEffect(() => {
    setSyncedAt(new Date())
  }, [])

  const syncLabel = syncedAt.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

  return (
    <footer className="mt-auto border-t border-border bg-surface">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-6 py-4">
        <p className="font-mono text-[11px] text-text-muted">
          © {new Date().getFullYear()} Berth Operations. All rights reserved.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-md border border-border bg-page-bg px-2 py-0.5 font-mono text-[11px] font-medium text-text-muted">
            v1.0.0
          </span>
          <span className="font-mono text-[11px] text-text-faint">
            마지막 동기화 {syncLabel}
          </span>
        </div>
      </div>
    </footer>
  )
}
