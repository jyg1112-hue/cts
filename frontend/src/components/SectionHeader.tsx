type SectionHeaderProps = {
  title: string
}

export function SectionHeader({ title }: SectionHeaderProps) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <h2 className="shrink-0 font-sans text-[13px] font-semibold tracking-[-0.01em] text-text">
        {title}
      </h2>
      <div className="h-px min-w-0 flex-1 bg-border" aria-hidden />
    </div>
  )
}
