import { Badge, type BadgeProps } from '@/components/ui/badge'

const VERDICT_TONE: Record<string, BadgeProps['tone']> = {
  'Strong fit': 'strong',
  'Possible fit': 'medium',
  'Weak fit': 'weak',
  'Not eligible': 'danger',
}

/** The backend's verdict tier as a badge. Renders nothing when there is no verdict. */
export function VerdictBadge({ verdict }: { verdict: string | null | undefined }) {
  if (!verdict) return null
  return <Badge tone={VERDICT_TONE[verdict] ?? 'neutral'}>{verdict}</Badge>
}
