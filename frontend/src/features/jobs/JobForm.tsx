import { ArrowRight } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { FileDropzone } from '@/components/ui/file-dropzone'
import { Textarea } from '@/components/ui/input'
import { SegmentedControl } from '@/components/ui/segmented-control'

/** Matches the backend's minimum for pasted job descriptions. */
export const MIN_JD_CHARS = 200

type Mode = 'pdf' | 'text'

/** The PDF exactly as it will be stored, rendered by the browser from the local file. */
function PdfPreview({ file }: { file: File }) {
  const url = useMemo(() => URL.createObjectURL(file), [file])
  useEffect(() => () => URL.revokeObjectURL(url), [url])
  return (
    <iframe
      title="Job description preview"
      src={url}
      className="h-[60vh] w-full rounded-lg border"
    />
  )
}

/**
 * Add a job: a PDF or pasted text on the left, a live preview of exactly what will be
 * added on the right (stacked on phones).
 */
export function JobForm(props: {
  onSubmit: (jd: File | string) => void
  pending: boolean
  error?: string
}) {
  const [mode, setMode] = useState<Mode>('pdf')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const length = text.trim().length
  const jd = mode === 'pdf' ? file : length >= MIN_JD_CHARS ? text : null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (jd) props.onSubmit(jd)
  }

  return (
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-medium">Job description</h2>
            <SegmentedControl
              label="Job description input"
              value={mode}
              onChange={setMode}
              options={[
                { value: 'pdf', label: 'PDF' },
                { value: 'text', label: 'Paste text' },
              ]}
            />
          </div>
          <fieldset disabled={props.pending} className="disabled:opacity-60">
            {mode === 'pdf' ? (
              <FileDropzone
                label="Job description PDF"
                hint="PDF · up to 10 MB"
                accept="application/pdf,.pdf"
                file={file}
                onChange={setFile}
              />
            ) : (
              <div className="space-y-1">
                <Textarea
                  aria-label="Job description text"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste the job description from the job portal…"
                  rows={12}
                />
                {length < MIN_JD_CHARS && (
                  <p className="text-xs text-muted-foreground">
                    {length} / {MIN_JD_CHARS} characters minimum
                  </p>
                )}
              </div>
            )}
          </fieldset>
          {props.error && (
            <p role="alert" className="text-sm text-destructive">
              {props.error}
            </p>
          )}
          <Button type="submit" size="lg" disabled={!jd || props.pending} className="w-full">
            {props.pending ? 'Adding…' : 'Add job'}
            {!props.pending && <ArrowRight aria-hidden />}
          </Button>
          <p className="text-xs text-muted-foreground">
            The requirements are read from it in the background; you can add candidates right away.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <h2 className="text-sm font-medium">Preview</h2>
          {mode === 'pdf' && file && <PdfPreview file={file} />}
          {mode === 'text' && length > 0 && (
            <pre
              aria-label="Job description preview"
              className="max-h-[60vh] overflow-auto rounded-lg border bg-muted/30 p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap"
            >
              {text.trim()}
            </pre>
          )}
          {!(mode === 'pdf' ? file : length > 0) && (
            <p className="rounded-lg border border-dashed px-4 py-16 text-center text-sm text-muted-foreground">
              {mode === 'pdf'
                ? 'Choose a PDF to see it here before adding it.'
                : 'Paste the text to see it here before adding it.'}
            </p>
          )}
        </CardContent>
      </Card>
    </form>
  )
}
