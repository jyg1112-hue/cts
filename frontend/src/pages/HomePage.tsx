import { FeatureCard } from '../components/FeatureCard'
import { SectionHeader } from '../components/SectionHeader'
import type { FeatureCardProps } from '../components/FeatureCard'

const operationsCards: Omit<FeatureCardProps, 'animationDelaySec'>[] = [
  {
    category: 'operations',
    icon: '📅',
    title: '7선석 하역 스케줄',
    description: '기준일 기반 선석별 스케줄 조회 및 관리',
    status: 'running',
    to: '/operations/schedule',
  },
  {
    category: 'operations',
    icon: '🚢',
    title: '반출 스케줄',
    description: 'CW1 / CW2 / Silo 반출 계획 수립',
    status: 'running',
    to: '/operations/export',
  },
  {
    category: 'operations',
    icon: '📊',
    title: '하역 데이터',
    description: '하역 실적 데이터 조회 및 분석',
    status: 'running',
    to: '/operations/data',
  },
  {
    category: 'operations',
    icon: '🏗️',
    title: '야드 현황 / 시뮬레이션',
    description: '반입·반출 기반 야드 상태 시뮬레이션',
    status: 'updating',
    to: '/operations/yard',
  },
]

const maintenanceCards: Omit<FeatureCardProps, 'animationDelaySec'>[] = [
  {
    category: 'maintenance',
    icon: '🔧',
    title: '장비 현황',
    description: '선석별 장비 가동 현황 및 상태 모니터링',
    status: 'preparing',
    disabled: true,
  },
  {
    category: 'maintenance',
    icon: '📋',
    title: '정비 이력',
    description: '장비별 정비 기록 조회 및 이력 관리',
    status: 'preparing',
    disabled: true,
  },
  {
    category: 'maintenance',
    icon: '🗓️',
    title: '정비 계획',
    description: '정비 일정 수립 및 알림 (준비 중)',
    status: 'preparing',
    disabled: true,
  },
]

export function HomePage() {
  let delayIndex = 0
  const nextDelay = () => {
    const d = delayIndex * 0.04
    delayIndex += 1
    return d
  }

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-1 px-6 pb-12 pt-10">
      <h1 className="mb-10 max-w-[720px] font-sans text-2xl font-semibold leading-snug tracking-[-0.02em] text-[#1a2236]">
        안녕하세요, 오늘도 안전한 하역 운영을 시작하세요.
      </h1>

      <section className="mb-12">
        <SectionHeader title="운영 관리" />
        <div className="grid grid-cols-4 gap-[14px]">
          {operationsCards.map((card) => (
            <FeatureCard
              key={card.title}
              {...card}
              animationDelaySec={nextDelay()}
            />
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="정비 관리" />
        <div className="grid grid-cols-4 gap-[14px]">
          {maintenanceCards.map((card) => (
            <FeatureCard
              key={card.title}
              {...card}
              animationDelaySec={nextDelay()}
            />
          ))}
          <div
            className="animate-card-enter min-h-[188px] rounded-[12px] border border-dashed border-border bg-transparent"
            style={{ animationDelay: `${nextDelay()}s` }}
            aria-hidden
          />
        </div>
      </section>
    </div>
  )
}
