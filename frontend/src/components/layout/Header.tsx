import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { AccountSettingsModal } from '../AccountSettingsModal'

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
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [now, setNow] = useState(() => new Date())
  const [accountOpen, setAccountOpen] = useState(false)
  const isPlatformAdmin = user?.id === 'admin'

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
          {isPlatformAdmin ? (
            <button
              type="button"
              onClick={() => setAccountOpen(true)}
              className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-text-muted transition hover:border-border hover:bg-page-bg hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ops"
              aria-label="계정 설정"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          ) : null}
          {user ? (
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/login', { replace: true })
              }}
              className="shrink-0 rounded-lg border border-border px-3 py-2 text-[13px] font-medium text-text-muted transition hover:border-border hover:bg-page-bg hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ops"
            >
              로그아웃
            </button>
          ) : null}
        </div>
      </div>
      {isPlatformAdmin ? (
        <AccountSettingsModal
          open={accountOpen}
          onClose={() => setAccountOpen(false)}
        />
      ) : null}
    </header>
  )
}
