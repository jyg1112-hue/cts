import { Link, useLocation } from 'react-router-dom'

const titles: Record<string, string> = {
  '/operations/schedule': '7선석 하역 스케줄',
  '/operations/export': '반출 스케줄',
  '/operations/data': '하역 데이터',
  '/operations/yard': '야드 현황 / 시뮬레이션',
  '/maintenance/equipment': '장비 현황',
  '/maintenance/history': '정비 이력',
}

export function FeaturePlaceholderPage() {
  const { pathname } = useLocation()
  const title = titles[pathname] ?? '기능'

  return (
    <div className="flex flex-1 flex-col bg-surface">
      <div className="mx-auto w-full max-w-[1200px] px-6 py-10">
        <div className="rounded-[12px] border border-border p-8">
          <h1 className="mb-2 font-sans text-xl font-semibold text-text">
            {title}
          </h1>
          <p className="mb-6 font-sans text-sm font-light text-text-muted">
            이 화면은 연결 준비 중입니다. 기존 HTML/백엔드와 붙일 때 이 라우트에
            실제 UI를 배치하면 됩니다.
          </p>
          <Link
            to="/"
            className="inline-flex font-sans text-sm font-medium text-ops underline-offset-4 hover:underline"
          >
            ← 메인으로
          </Link>
        </div>
      </div>
    </div>
  )
}
