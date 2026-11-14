import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { ScoreRing } from '@/components/score/score-ring'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { JdHistoryItem } from './api'
import { JdRuns } from './JdRuns'

function JdCard({ jd }: { jd: JdHistoryItem }) {
  const [open, setOpen] = useState(false)
  const panelId = `jd-runs-${jd.jd_document_id}`
  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-4 p-4 text-left transition-colors hover:bg-muted/40 sm:p-5"
      >
        <ScoreRing score={jd.best_score} size="sm" />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="truncate font-medium">{jd.title}</p>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <Badge tone="outline">{jd.source === 'text' ? 'Pasted text' : 'PDF'}</Badge>
            <span>
              {jd.run_count} {jd.run_count === 1 ? 'resume' : 'resumes'} · best {jd.best_score}
            </span>
            <span>Last scored {formatDateTime(jd.last_scored_at)}</span>
          </div>
        </div>
        <ChevronDown
          className={cn(
            'size-5 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>
      {open && (
        <div id={panelId} className="border-t">
          <JdRuns jdDocumentId={jd.jd_document_id} />
        </div>
      )}
    </Card>
  )
}

/** Every JD that has been scored, most recent first; expand one to see its resumes. */
export function JdHistoryList({ jds }: { jds: JdHistoryItem[] }) {
  return (
    <div className="space-y-3">
      {jds.map((jd) => (
        <JdCard key={jd.jd_document_id} jd={jd} />
      ))}
    </div>
  )
}
