import { CircleAlert, CircleCheck, type LucideIcon } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import type { Point } from './api'

function PointCard(props: {
  title: string
  points: Point[]
  Icon: LucideIcon
  iconClass: string
  empty: string
}) {
  const { Icon } = props
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className={cn('size-5', props.iconClass)} aria-hidden />
          {props.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {props.points.length === 0 ? (
          <p className="text-sm text-muted-foreground">{props.empty}</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {props.points.map((p) => (
              <li key={p.source} className="flex gap-2.5">
                <span
                  aria-hidden
                  className={cn('mt-2 size-1.5 shrink-0 rounded-full bg-current', props.iconClass)}
                />
                <span>{p.text}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

/** Key takeaways, scorecard style: strengths and concerns side by side. */
export function Takeaways({ pros, cons }: { pros: Point[]; cons: Point[] }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <PointCard
        title="Strengths"
        points={pros}
        Icon={CircleCheck}
        iconClass="text-score-strong"
        empty="No clear strengths against this JD."
      />
      <PointCard
        title="Concerns"
        points={cons}
        Icon={CircleAlert}
        iconClass="text-score-medium"
        empty="No concerns found."
      />
    </div>
  )
}
