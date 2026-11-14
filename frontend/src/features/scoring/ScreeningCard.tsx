import { MessageCircleQuestion } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import type { RunDetail } from './api'

/** Requirements the resume is silent on that a recruiter would simply ask about. */
export function ScreeningCard({ items }: { items: RunDetail['screening'] }) {
  if (items.length === 0) return null
  return (
    <Card className="border-score-medium/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageCircleQuestion className="size-5 text-score-medium" aria-hidden />
          Questions for the screening call
        </CardTitle>
        <CardDescription>
          The resume doesn&apos;t say, so these don&apos;t count for or against the score yet.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3 text-sm">
          {items.map((item) => (
            <li key={item.key}>
              <p className="font-medium">{item.name}</p>
              <p className="text-muted-foreground">{item.reasoning}</p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
