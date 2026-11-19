import { UploadCloud } from 'lucide-react'
import { useId, useRef, useState, type DragEvent } from 'react'

import { cn } from '@/lib/utils'

/**
 * Drop area for one or many files at once; hands them over immediately (no chip).
 * Keyboard / click fallback via the hidden <input type="file" multiple>.
 */
export function FilesDropzone(props: {
  label: string
  hint: string
  accept: string
  onFiles: (files: File[]) => void
  disabled?: boolean
  compact?: boolean
}) {
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function take(list: FileList | null | undefined) {
    const files = Array.from(list ?? [])
    if (files.length && !props.disabled) props.onFiles(files)
    if (input.current) input.current.value = ''
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    take(event.dataTransfer.files)
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
      aria-disabled={props.disabled}
      className={cn(
        'flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed px-4 text-center transition-colors',
        props.compact ? 'flex-wrap gap-x-3 py-3.5' : 'flex-col py-8',
        'hover:border-primary/50 hover:bg-accent/40 has-[:focus-visible]:border-primary has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/30',
        dragging && 'border-primary bg-accent/60',
        props.disabled && 'pointer-events-none opacity-60',
      )}
    >
      <UploadCloud
        className={cn('text-muted-foreground', props.compact ? 'size-5' : 'size-6')}
        aria-hidden
      />
      <span className="text-sm">
        <span className="font-medium text-primary">Choose files</span> or drag them here
      </span>
      <span className="text-xs text-muted-foreground">{props.hint}</span>
      <input
        ref={input}
        id={id}
        type="file"
        multiple
        accept={props.accept}
        aria-label={props.label}
        disabled={props.disabled}
        className="sr-only"
        onChange={(e) => take(e.target.files)}
      />
    </label>
  )
}
