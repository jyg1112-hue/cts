import { useEffect, useId } from 'react'
import { createPortal } from 'react-dom'
import { useAuth } from '../auth/AuthContext'

/** 헤더에서 관리자(admin)만 열 수 있음 — 별도 관리자 비밀번호 게이트 없음(백엔드 8000 앱과 동일 UX). */
export function AccountSettingsModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { user, logout } = useAuth()
  const titleId = useId()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const modal = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4"
      role="presentation"
      onMouseDown={(ev) => {
        if (ev.target === ev.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-[420px] rounded-2xl border border-border bg-surface p-6 shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className="mb-4 text-lg font-semibold text-text">
          계정 설정
        </h2>
        <div className="flex flex-col gap-4">
          <dl className="rounded-lg border border-border bg-page-bg px-4 py-3 text-[14px]">
            <div className="flex justify-between gap-4 py-1">
              <dt className="text-text-muted">로그인 아이디</dt>
              <dd className="font-medium text-text">{user?.id ?? '—'}</dd>
            </div>
          </dl>
          <p className="text-[13px] text-text-muted">
            계정·감사 로그 관리는 FastAPI 메인(
            <code className="rounded bg-page-bg px-1">localhost:8000</code>) 톱니바퀴에서
            관리자 로그인 비밀번호로 진입할 수 있습니다.
          </p>
          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={() => {
                logout()
                onClose()
              }}
              className="rounded-lg border border-border bg-surface px-4 py-2 text-[14px] font-medium text-text hover:bg-page-bg"
            >
              로그아웃
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg bg-[#003d7a] px-4 py-2 text-[14px] font-semibold text-white hover:bg-[#002f5e]"
            >
              닫기
            </button>
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(modal, document.body)
}
