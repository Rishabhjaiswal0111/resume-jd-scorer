import { Component, type ErrorInfo, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Catches render errors so one broken page doesn't blank the whole app.
 * Shows the request id for API errors so the matching backend log line is easy to find.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error boundary caught:', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    const requestId = error instanceof ApiError ? error.requestId : null
    return (
      <div role="alert" className="mx-auto max-w-xl space-y-3 p-8">
        <h2 className="text-lg font-semibold">Something went wrong on this page</h2>
        <p className="text-sm text-muted-foreground">{error.message}</p>
        {requestId && (
          <p className="text-xs text-muted-foreground">
            Request ID: <code className="select-all">{requestId}</code>
          </p>
        )}
        <Button variant="outline" onClick={() => this.setState({ error: null })}>
          Try again
        </Button>
      </div>
    )
  }
}
