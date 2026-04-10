export type CardStatus = 'running' | 'updating' | 'preparing'

const labels: Record<CardStatus, string> = {
  running: '운영중',
  updating: '업데이트 중',
  preparing: '준비 중',
}

type StatusBadgeProps = {
  status: CardStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const dotClass =
    status === 'running'
      ? 'bg-status-ok'
      : status === 'updating'
        ? 'bg-status-warn'
        : 'bg-text-faint'

  if (status === 'preparing') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-text-faint px-2 py-0.5">
        <span className={`size-[5px] shrink-0 rounded-full ${dotClass}`} />
        <span className="font-mono text-[11px] font-medium text-text-muted">
          {labels[status]}
        </span>
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`size-[5px] shrink-0 rounded-full ${dotClass}`} />
      <span className="font-mono text-[11px] font-medium text-text-muted">
        {labels[status]}
      </span>
    </span>
  )
}
