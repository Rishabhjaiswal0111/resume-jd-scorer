import { FileSearch, ListChecks, type LucideIcon, ScanText } from 'lucide-react'

const STEPS: { Icon: LucideIcon; title: string; text: string }[] = [
  {
    Icon: ScanText,
    title: 'Reads both documents',
    text: 'Text is extracted from the PDFs; contact details are removed before anything is analysed.',
  },
  {
    Icon: ListChecks,
    title: 'Builds the criteria',
    text: 'The job description becomes a checklist of must-haves, preferences and red flags.',
  },
  {
    Icon: FileSearch,
    title: 'Grades with evidence',
    text: 'Each requirement is checked against the resume and explained, then scored with fixed weights.',
  },
]

/** A short explainer under the form, shown before the first score. */
export function HowItWorks() {
  return (
    <section aria-label="How it works" className="grid gap-4 sm:grid-cols-3">
      {STEPS.map(({ Icon, title, text }) => (
        <div key={title} className="flex gap-3 sm:flex-col">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-accent-foreground">
            <Icon className="size-4" aria-hidden />
          </span>
          <div className="space-y-1">
            <p className="text-sm font-medium">{title}</p>
            <p className="text-sm text-muted-foreground">{text}</p>
          </div>
        </div>
      ))}
    </section>
  )
}
