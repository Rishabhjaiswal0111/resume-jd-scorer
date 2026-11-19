import { ExternalLink } from 'lucide-react'
import { useState } from 'react'

import { SegmentedControl } from '@/components/ui/segmented-control'
import { cn } from '@/lib/utils'

type View = 'document' | 'text'

/**
 * A stored document shown in the page: the original PDF (browser viewer) or its text.
 * Text is the default on small screens, where mobile browsers don't render PDFs inline.
 */
export function DocumentPreview(props: {
  title: string
  /** URL of the original (PDF or plain text). Omit to show text only. */
  src?: string
  isPdf: boolean
  text: string
  className?: string
}) {
  const wide = typeof window !== 'undefined' && window.matchMedia?.('(min-width: 768px)').matches
  const [view, setView] = useState<View>(props.isPdf && props.src && wide ? 'document' : 'text')
  const showPdf = props.isPdf && props.src && view === 'document'
  return (
    <div className={cn('space-y-3', props.className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {props.isPdf && props.src ? (
          <SegmentedControl
            label={`${props.title} view`}
            value={view}
            onChange={setView}
            options={[
              { value: 'document', label: 'PDF' },
              { value: 'text', label: 'Text' },
            ]}
          />
        ) : (
          <span className="text-xs text-muted-foreground">Text</span>
        )}
        {props.src && (
          <a
            href={props.src}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            Open original <ExternalLink className="size-3.5" aria-hidden />
          </a>
        )}
      </div>
      {showPdf ? (
        <iframe
          title={props.title}
          src={props.src}
          className="h-[70vh] w-full rounded-lg border bg-muted"
        />
      ) : (
        <pre
          aria-label={props.title}
          className="max-h-[70vh] overflow-auto rounded-lg border bg-muted/30 p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap"
        >
          {props.text}
        </pre>
      )}
    </div>
  )
}
