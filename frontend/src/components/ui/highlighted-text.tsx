import { Fragment } from 'react'

const START = '\u0001'
const END = '\u0002'

/**
 * Text with highlighted spans marked by \u0001 ... \u0002 (as the search API returns them).
 * Rendered as React elements, never as HTML, so resume text can't inject markup.
 */
export function HighlightedText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(START)
  return (
    <span className={className}>
      {parts.map((part, i) => {
        if (i === 0) return <Fragment key={i}>{part}</Fragment>
        const [marked, rest = ''] = part.split(END)
        return (
          <Fragment key={i}>
            <mark className="rounded-sm bg-accent px-0.5 text-accent-foreground">{marked}</mark>
            {rest}
          </Fragment>
        )
      })}
    </span>
  )
}
