import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Score a resume against a JD</h1>
        <p className="text-muted-foreground">
          Upload a job description and a resume (PDF) to get a score, pros, cons and the run cost.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Coming in Phase 3</CardTitle>
          <CardDescription>
            The upload form and results page are built once the scoring API exists (Phases 1–2).
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          The badge in the header confirms the frontend can reach the backend.
        </CardContent>
      </Card>
    </div>
  )
}
