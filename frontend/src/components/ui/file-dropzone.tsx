import { FileText, UploadCloud, X } from 'lucide-react'
import { useId, useRef, useState, type DragEvent } from 'react'

import { cn } from '@/lib/utils'

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.ceil(bytes / 1024)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * Drag-and-drop file picker with a click / keyboard fallback and a chip for the chosen file.
 * The hidden <input type="file"> keeps native behaviour and is what `label` names.
 */
export function FileDropzone(props: {
  label: string
  hint: string
  accept: string
  file: File | null
  onChange: (file: File | null) => void
}) {
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) props.onChange(dropped)
  }

  if (props.file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-md bg-accent text-accent-foreground">
          <FileText className="size-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{props.file.name}</p>
          <p className="text-xs text-muted-foreground">{formatSize(props.file.size)}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            props.onChange(null)
            if (input.current) input.current.value = ''
          }}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label={`Remove ${props.file.name}`}
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
    )
  }

  return (
    <label
      htmlFor={id}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors',
        'hover:border-primary/50 hover:bg-accent/40 has-[:focus-visible]:border-primary has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/30',
        dragging && 'border-primary bg-accent/60',
      )}
    >
      <UploadCloud className="size-6 text-muted-foreground" aria-hidden />
      <span className="text-sm">
        <span className="font-medium text-primary">Choose a file</span> or drag it here
      </span>
      <span className="text-xs text-muted-foreground">{props.hint}</span>
      <input
        ref={input}
        id={id}
        type="file"
        accept={props.accept}
        aria-label={props.label}
        className="sr-only"
        onChange={(e) => props.onChange(e.target.files?.[0] ?? null)}
      />
    </label>
  )
}
