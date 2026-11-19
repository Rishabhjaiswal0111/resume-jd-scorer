import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ApiError } from '@/lib/api/client'

const FRIENDLY: Record<string, string> = {
  PDF_UNREADABLE: "Couldn't read one of the PDFs.",
  PDF_SCANNED: 'One of the PDFs is a scan with no text layer; OCR is not enabled yet.',
  PDF_TOO_LARGE: 'One of the PDFs is too large (max 10 MB, 20 pages).',
  RUBRIC_EMPTY: 'No requirements were found in the job description.',
  LLM_NOT_CONFIGURED: 'No LLM is configured. Add an API key to .env.',
  LLM_RESPONSE_PENDING:
    'Still waiting for the manual answer after ~15 minutes. Ask Claude Code to answer the pending prompt (make pending), then click Retry.',
}

export function ScoreError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const api = error instanceof ApiError ? error : null
  const pending = api?.code === 'LLM_RESPONSE_PENDING'
  return (
    <Card className={pending ? 'border-score-medium' : 'border-destructive'}>
      <CardContent className="space-y-2 pt-6 text-sm" role="alert">
        <p className="font-medium">{(api && FRIENDLY[api.code]) ?? error.message}</p>
        {api && (
          <p className="text-muted-foreground">
            {api.code}: {api.message}
            {api.requestId && <> · request {api.requestId}</>}
          </p>
        )}
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </CardContent>
    </Card>
  )
}
