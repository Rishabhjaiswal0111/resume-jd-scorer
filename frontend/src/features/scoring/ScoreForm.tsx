import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

import type { ScoreInput } from './api'

interface ScoreFormProps {
  onSubmit: (input: ScoreInput) => void
  pending: boolean
}

function FileField(props: {
  id: string
  label: string
  file: File | null
  onChange: (file: File | null) => void
}) {
  return (
    <label htmlFor={props.id} className="flex flex-1 flex-col gap-2 text-sm font-medium">
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

export function ScoreForm({ onSubmit, pending }: ScoreFormProps) {
  const [jd, setJd] = useState<File | null>(null)
  const [resume, setResume] = useState<File | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (jd && resume) onSubmit({ jd, resume })
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <FileField id="jd" label="Job description (PDF)" file={jd} onChange={setJd} />
          <FileField id="resume" label="Resume (PDF)" file={resume} onChange={setResume} />
          <Button type="submit" disabled={!jd || !resume || pending}>
            {pending ? 'Scoring…' : 'Score'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
