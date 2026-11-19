import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { HighlightedText } from '@/components/ui/highlighted-text'
import { cn } from '@/lib/utils'

import type { SearchHit } from './api'

function MatchMeter({ value }: { value: number }) {
  return (
    <div className="w-20 shrink-0 space-y-1 text-right" aria-label={`${value}% match`}>
      <p className="text-sm font-semibold tabular-nums">{value}%</p>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

/** One search result: who, how well the text matched, where, and which jobs they're on. */
export function SearchHitRow(props: { hit: SearchHit; selected: boolean; onToggle: () => void }) {
  const { hit } = props
  const c = hit.candidate
  const matched = hit.terms.filter((t) => t.matched)
  const missing = hit.terms.filter((t) => !t.matched)
  return (
    <li className={cn('flex gap-3 p-4 sm:px-5', props.selected && 'bg-accent/40')}>
      <input
        type="checkbox"
        checked={props.selected}
        onChange={props.onToggle}
        aria-label={`Select ${c.name}`}
        className="mt-1 size-4 shrink-0 accent-primary"
      />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="font-medium">{c.name}</p>
            {c.headline && (
              <p className="line-clamp-2 text-sm text-muted-foreground sm:line-clamp-1">
                {c.headline}
              </p>
            )}
          </div>
          <MatchMeter value={hit.match} />
        </div>
        <div className="flex flex-wrap gap-1" aria-label="Matched terms">
          {matched.slice(0, 12).map((t) => (
            <Badge key={t.term} tone="accent">
              {t.term}
            </Badge>
          ))}
          {missing.slice(0, 6).map((t) => (
            <Badge key={t.term} tone="outline" className="line-through opacity-70">
              {t.term}
            </Badge>
          ))}
          {matched.length + missing.length > 18 && (
            <span className="text-xs text-muted-foreground">
              {matched.length} of {matched.length + missing.length} terms
            </span>
          )}
        </div>
        {hit.snippet && (
          <p className="line-clamp-3 text-sm text-muted-foreground">
            <HighlightedText text={hit.snippet} />
          </p>
        )}
        {hit.jobs.length > 0 && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            On:
            {hit.jobs.map((j) => (
              <Link
                key={j.job_candidate_id}
                to={`/jobs/${j.job_id}/candidates/${j.job_candidate_id}`}
                className="font-medium text-primary hover:underline"
              >
                {j.job_title}
                {j.score !== null ? ` · ${j.score}` : ` · ${j.status}`}
              </Link>
            ))}
          </p>
        )}
      </div>
    </li>
  )
}
