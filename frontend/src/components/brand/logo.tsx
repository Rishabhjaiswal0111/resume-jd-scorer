import { uiConfig } from '@/config/ui'

/** Brand mark + name. The mark: two overlapping documents with a check (JD x resume). */
export function Logo({ showName = true }: { showName?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden>
        <rect x="2" y="2" width="28" height="28" rx="8" className="fill-primary" />
        <rect x="8" y="8" width="11" height="14" rx="2" className="fill-primary-foreground/35" />
        <rect x="13" y="11" width="11" height="14" rx="2" className="fill-primary-foreground" />
        <path
          d="M15.8 18.4l2.1 2.1 3.9-4.3"
          fill="none"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="stroke-primary"
        />
      </svg>
      {showName && (
        <span className="font-semibold tracking-tight whitespace-nowrap">{uiConfig.appName}</span>
      )}
    </span>
  )
}
