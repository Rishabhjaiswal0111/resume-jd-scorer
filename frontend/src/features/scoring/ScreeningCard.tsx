import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import type { RunDetail } from './api'

/** Requirements the resume is silent on that a recruiter would simply ask about. */
export function ScreeningCard({ items }: { items: RunDetail['screening'] }) {
  if (items.length === 0) return null
  return (
    <Card className="border-score-medium">
      <CardHeader>
        <CardTitle>Ask in screening</CardTitle>
        <CardDescription>
          The resume doesn&apos;t say; these are left out of the score until confirmed.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {items.map((item) => (
            <li key={item.key}>
              <span className="font-medium">{item.name}</span>
              <span className="text-muted-foreground"> · {item.reasoning}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
