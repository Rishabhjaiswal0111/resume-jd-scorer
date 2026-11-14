import { ArrowRight } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { FileDropzone } from '@/components/ui/file-dropzone'
import { SegmentedControl } from '@/components/ui/segmented-control'

import type { ScoreInput } from './api'

/** Matches the backend's minimum for pasted job descriptions. */
export const MIN_JD_CHARS = 200
const PDF_HINT = 'PDF · up to 10 MB'

type JdMode = 'pdf' | 'text'

function Step(props: { n: number; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex min-h-7 items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <span className="grid size-5 place-items-center rounded-full bg-accent text-xs text-accent-foreground">
            {props.n}
          </span>
          {props.title}
        </h2>
        {props.aside}
      </div>
      {props.children}
    </section>
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
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Locked while scoring so the inputs can't change under a running request. */}
          <fieldset disabled={pending} className="grid gap-6 disabled:opacity-60 md:grid-cols-2">
            <Step
              n={1}
              title="Job description"
              aside={
                <SegmentedControl
                  label="Job description input"
                  value={mode}
                  onChange={setMode}
                  options={[
                    { value: 'pdf', label: 'PDF' },
                    { value: 'text', label: 'Paste text' },
                  ]}
                />
              }
            >
              {mode === 'pdf' ? (
                <FileDropzone
                  label="Job description PDF"
                  hint={PDF_HINT}
                  accept="application/pdf,.pdf"
                  file={jdFile}
                  onChange={setJdFile}
                />
              ) : (
                <div className="space-y-1">
                  <textarea
                    aria-label="Job description text"
                    value={jdText}
                    onChange={(e) => setJdText(e.target.value)}
                    placeholder="Paste the job description from the job portal…"
                    rows={7}
                    className="w-full rounded-lg border bg-card p-3 text-sm focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none"
                  />
                  {textLength < MIN_JD_CHARS && (
                    <p className="text-xs text-muted-foreground">
                      {textLength} / {MIN_JD_CHARS} characters minimum
                    </p>
                  )}
                </div>
              )}
            </Step>
            <Step n={2} title="Resume">
              <FileDropzone
                label="Resume (PDF)"
                hint={PDF_HINT}
                accept="application/pdf,.pdf"
                file={resume}
                onChange={setResume}
              />
            </Step>
          </fieldset>
          <div className="flex justify-end">
            <Button
              type="submit"
              size="lg"
              disabled={!jd || !resume || pending}
              className="w-full md:w-auto"
            >
              {pending ? 'Scoring…' : 'Score'}
              {!pending && <ArrowRight aria-hidden />}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
