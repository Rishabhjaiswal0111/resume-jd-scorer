import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { JobDetail, JobRequirement } from './api'

const GROUPS: { title: string; operators: string[] }[] = [
  { title: 'Must-haves', operators: ['must_have'] },
  { title: 'Preferred', operators: ['preferred'] },
  { title: 'Nice to have', operators: ['nice_to_have'] },
  { title: 'Red flags', operators: ['must_avoid', 'may_avoid'] },
]

function Requirement({ r }: { r: JobRequirement }) {
  return (
    <li className="space-y-1 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{r.name}</span>
        {r.knockout && <Badge tone="danger">Deal-breaker</Badge>}
        {r.verify_in_screening && <Badge tone="outline">Ask in screening</Badge>}
        {r.importance === 'high' && <Badge tone="accent">Key</Badge>}
      </div>
      {r.values.length > 0 && (
        <p className="text-xs text-muted-foreground">{r.values.join(' · ')}</p>
      )}
    </li>
  )
}

/** What the AI read out of the JD: what each candidate is graded on. */
export function Requirements({ job }: { job: JobDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>What candidates are graded on</CardTitle>
        {job.role_summary && <p className="text-sm text-muted-foreground">{job.role_summary}</p>}
        {job.core_requirement && (
          <p className="text-sm">
            <span className="font-medium">Core requirement: </span>
            {job.core_requirement}
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-5">
        {GROUPS.map((group) => {
          const items = job.requirements.filter((r) => group.operators.includes(r.operator))
          if (!items.length) return null
          return (
            <section key={group.title}>
              <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {group.title} <span className="tabular-nums">({items.length})</span>
              </h3>
              <ul className="divide-y">
                {items.map((r) => (
                  <Requirement key={r.key} r={r} />
                ))}
              </ul>
            </section>
          )
        })}
      </CardContent>
    </Card>
  )
}
