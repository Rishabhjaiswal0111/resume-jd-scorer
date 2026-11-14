/**
 * Score bands shared by every score display. Thresholds match the backend verdict tiers
 * (engine 1.1+: >= 75 Strong fit, >= 50 Possible fit, otherwise Weak fit).
 */
export type ScoreBand = 'strong' | 'medium' | 'weak'

export function scoreBand(score: number): ScoreBand {
  if (score >= 75) return 'strong'
  if (score >= 50) return 'medium'
  return 'weak'
}

/** Text-colour class for a band (tokens only). */
export const BAND_TEXT: Record<ScoreBand, string> = {
  strong: 'text-score-strong',
  medium: 'text-score-medium',
  weak: 'text-score-weak',
}

export const BAND_STROKE: Record<ScoreBand, string> = {
  strong: 'stroke-score-strong',
  medium: 'stroke-score-medium',
  weak: 'stroke-score-weak',
}
