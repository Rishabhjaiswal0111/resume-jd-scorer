import { cn } from '@/lib/utils'

import { BAND_STROKE, BAND_TEXT, scoreBand } from './score-band'

const SIZES = {
  sm: { box: 40, stroke: 4, text: 'text-xs' },
  lg: { box: 104, stroke: 8, text: 'text-3xl' },
} as const

/** A score (0-100) as a ring that fills to the score, coloured by band. */
export function ScoreRing({
  score,
  size = 'lg',
  className,
}: {
  score: string | null
  size?: keyof typeof SIZES
  className?: string
}) {
  const value = Number(score ?? 0)
  const { box, stroke, text } = SIZES[size]
  const radius = (box - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const band = scoreBand(value)
  return (
    <div
      className={cn('relative inline-grid shrink-0 place-items-center', className)}
      style={{ width: box, height: box }}
      role="img"
      aria-label={`Score ${score ?? 'unknown'} out of 100`}
    >
      <svg width={box} height={box} className="-rotate-90" aria-hidden>
        <circle
          cx={box / 2}
          cy={box / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-muted"
        />
        <circle
          cx={box / 2}
          cy={box / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - Math.min(100, Math.max(0, value)) / 100)}
          className={BAND_STROKE[band]}
        />
      </svg>
      <span className={cn('absolute font-semibold tabular-nums', text, BAND_TEXT[band])}>
        {score ?? '–'}
      </span>
    </div>
  )
}
