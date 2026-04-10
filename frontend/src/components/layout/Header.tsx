import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const WEEKDAYS_KO = ['일', '월', '화', '수', '목', '금', '토'] as const

function formatDateTime(d: Date) {
  const y = d.getFullYear()
  const mo = d.getMonth() + 1
  const day = d.getDate()
  const w = WEEKDAYS_KO[d.getDay()]
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${y}.${mo}.${day}(${w}) ${h}:${mi}:${s}`
}

export function Header() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <header className="sticky top-0 z-50 h-[60px] border-b border-border bg-surface">
      <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
        <Link to="/" className="flex min-w-0 items-center gap-3 no-underline">
          <span className="truncate font-sans text-[15px] font-semibold text-text">
            선석 운영 플랫폼
          </span>
          <span
            className="hidden h-4 w-px shrink-0 bg-border sm:block"
            aria-hidden
          />
          <span className="font-mono text-[11px] font-medium tracking-[0.08em] text-text-muted max-sm:hidden">
            BERTH OPERATIONS
          </span>
        </Link>

        <div className="flex shrink-0 items-center gap-4">
          <div className="flex items-center gap-2 rounded-full border border-border bg-page-bg px-2.5 py-1">
            <span
              className="size-[5px] shrink-0 rounded-full bg-status-ok animate-live-dot"
              aria-hidden
            />
            <span className="font-mono text-[11px] font-medium text-text-muted">
              시스템 정상
            </span>
          </div>
          <time
            dateTime={now.toISOString()}
            className="whitespace-nowrap font-mono text-[12px] font-medium tabular-nums text-text"
          >
            {formatDateTime(now)}
          </time>
        </div>
      </div>
    </header>
  )
}
