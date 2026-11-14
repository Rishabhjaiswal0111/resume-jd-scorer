import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import type { ScoreInput } from './api'

/** Matches the backend's minimum for pasted job descriptions. */
export const MIN_JD_CHARS = 200

type JdMode = 'pdf' | 'text'

function PdfField(props: { id: string; label: string; onChange: (file: File | null) => void }) {
  return (
    <label htmlFor={props.id} className="flex flex-col gap-2 text-sm font-medium">
      {props.label}
      <input
        id={props.id}
        type="file"
        accept="application/pdf,.pdf"
        onChange={(e) => props.onChange(e.target.files?.[0] ?? null)}
        className="rounded-md border p-2 text-sm font-normal file:mr-3 file:rounded file:border-0 file:bg-secondary file:px-3 file:py-1"
      />
    </label>
  )
}

function ModeToggle({ mode, onChange }: { mode: JdMode; onChange: (mode: JdMode) => void }) {
  const options: { value: JdMode; label: string }[] = [
    { value: 'pdf', label: 'PDF' },
    { value: 'text', label: 'Paste text' },
  ]
  return (
    <div role="radiogroup" aria-label="Job description input" className="flex gap-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={mode === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-md px-2 py-1 text-xs',
            mode === o.value ? 'bg-secondary font-medium' : 'text-muted-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function ScoreForm({
  onSubmit,
  pending,
}: {
  onSubmit: (input: ScoreInput) => void
  pending: boolean
}) {
  const [mode, setMode] = useState<JdMode>('pdf')
  const [jdFile, setJdFile] = useState<File | null>(null)
  const [jdText, setJdText] = useState('')
  const [resume, setResume] = useState<File | null>(null)

  const textLength = jdText.trim().length
  const jd = mode === 'pdf' ? jdFile : textLength >= MIN_JD_CHARS ? jdText : null

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (jd && resume) onSubmit({ jd, resume })
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Job description</span>
              <ModeToggle mode={mode} onChange={setMode} />
            </div>
            {mode === 'pdf' ? (
              <PdfField id="jd" label="Job description PDF" onChange={setJdFile} />
            ) : (
              <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                <span className="sr-only">Job description text</span>
                <textarea
                  aria-label="Job description text"
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  placeholder="Paste the job description from the job portal…"
                  rows={10}
                  className="rounded-md border p-2 text-sm text-foreground"
                />
                {textLength < MIN_JD_CHARS && `${textLength} / ${MIN_JD_CHARS} characters minimum`}
              </label>
            )}
          </div>
          <div className="flex flex-col justify-between gap-4">
            <PdfField id="resume" label="Resume (PDF)" onChange={setResume} />
            <Button type="submit" disabled={!jd || !resume || pending} className="self-end">
              {pending ? 'Scoring…' : 'Score'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
