import { Link } from 'react-router-dom'
import type { CardStatus } from './StatusBadge'
import { StatusBadge } from './StatusBadge'

export type FeatureCategory = 'operations' | 'maintenance'

export type FeatureCardProps = {
  category: FeatureCategory
  icon: string
  title: string
  description: string
  status: CardStatus
  to?: string
  disabled?: boolean
  animationDelaySec: number
}

const topBorder: Record<FeatureCategory, string> = {
  operations: 'border-t-ops',
  maintenance: 'border-t-mx',
}

const iconBg: Record<FeatureCategory, string> = {
  operations: 'bg-ops-bg border border-ops-border',
  maintenance: 'bg-mx-bg border border-mx-border',
}

const hoverShadow: Record<FeatureCategory, string> = {
  operations: 'hover:shadow-[0_10px_28px_-8px_rgba(37,99,235,0.22)]',
  maintenance: 'hover:shadow-[0_10px_28px_-8px_rgba(5,150,105,0.22)]',
}

const baseClass =
  'animate-card-enter flex flex-col rounded-[12px] border border-border bg-surface pt-[2px] shadow-none transition-[transform,box-shadow] duration-[180ms] ease-out px-[22px] pb-[18px] pt-5 text-left no-underline'

export function FeatureCard({
  category,
  icon,
  title,
  description,
  status,
  to,
  disabled = false,
  animationDelaySec,
}: FeatureCardProps) {
  const isInteractive = Boolean(to) && !disabled

  const composed = [
    baseClass,
    topBorder[category],
    isInteractive
      ? `cursor-pointer hover:-translate-y-0.5 ${hoverShadow[category]} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ops`
      : 'cursor-default opacity-90',
  ].join(' ')

  const style = { animationDelay: `${animationDelaySec}s` } as const

  const inner = (
    <>
      <div
        className={`mb-3 flex size-10 items-center justify-center rounded-[10px] text-[20px] leading-none ${iconBg[category]}`}
        aria-hidden
      >
        {icon}
      </div>
      <h3 className="mb-1.5 font-sans text-[14px] font-semibold text-text">
        {title}
      </h3>
      <p className="mb-4 font-sans text-[12px] font-light leading-[1.45] text-text-muted">
        {description}
      </p>
      <div className="mb-3 h-px w-full bg-border" aria-hidden />
      <div className="mt-auto flex items-center justify-between gap-2">
        <StatusBadge status={status} />
        <span
          className={`font-mono text-[14px] font-medium ${isInteractive ? 'text-text-muted' : 'text-text-faint'}`}
          aria-hidden
        >
          ↗
        </span>
      </div>
    </>
  )

  if (isInteractive && to) {
    return (
      <Link to={to} className={composed} style={style}>
        {inner}
      </Link>
    )
  }

  return (
    <article className={composed} style={style}>
      {inner}
    </article>
  )
}
