import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ??
    '/'

  const [id, setId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  if (user) {
    return <Navigate to={from} replace />
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!id.trim()) {
      setError('아이디를 입력해 주세요.')
      return
    }
    if (!password) {
      setError('비밀번호를 입력해 주세요.')
      return
    }
    login(id.trim(), password)
    navigate(from, { replace: true })
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-page-bg px-4 py-12">
      <div className="w-full max-w-[400px] rounded-2xl border border-border bg-surface px-8 py-10 shadow-sm">
        <div className="mb-10 flex justify-center">
          <img
            src="/posco-flow-logo.jpg"
            alt="posco FLOW"
            width={280}
            height={113}
            className="h-auto max-h-[120px] w-full max-w-[280px] object-contain"
            decoding="async"
            fetchPriority="high"
          />
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div>
            <label
              htmlFor="login-id"
              className="mb-1.5 block text-[13px] font-medium text-text-muted"
            >
              아이디
            </label>
            <input
              id="login-id"
              name="username"
              type="text"
              autoComplete="username"
              value={id}
              onChange={(e) => setId(e.target.value)}
              className="w-full rounded-lg border border-border bg-page-bg px-3.5 py-2.5 text-[15px] text-text outline-none ring-ops/20 transition placeholder:text-text-faint focus:border-ops focus:ring-2"
              placeholder="아이디"
            />
          </div>
          <div>
            <label
              htmlFor="login-password"
              className="mb-1.5 block text-[13px] font-medium text-text-muted"
            >
              비밀번호
            </label>
            <input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-page-bg px-3.5 py-2.5 text-[15px] text-text outline-none ring-ops/20 transition placeholder:text-text-faint focus:border-ops focus:ring-2"
              placeholder="비밀번호"
            />
          </div>

          {error ? (
            <p className="text-[13px] text-red-600" role="alert">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            className="mt-1 rounded-lg bg-[#003d7a] py-3 text-[15px] font-semibold text-white transition hover:bg-[#002f5e] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#003d7a]"
          >
            로그인
          </button>
        </form>
      </div>
    </div>
  )
}
