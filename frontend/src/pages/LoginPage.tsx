import { ArrowRight, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router'

import { Logo } from '@/components/brand/logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useDemoInfo, useLogin, useMe } from '@/features/auth/api'

/** Only same-site paths, so ?next= can't send someone to another site after sign-in. */
function safeNext(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : '/jobs'
}

export function LoginPage() {
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const navigate = useNavigate()
  const me = useMe()
  const demo = useDemoInfo()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  if (me.data) return <Navigate to={next} replace />

  function signIn(credentials: { email: string; password: string }) {
    login.mutate(credentials, { onSuccess: () => navigate(next, { replace: true }) })
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    signIn({ email, password })
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4 py-10">
      <Logo />
      <Card className="w-full max-w-sm">
        <CardContent className="space-y-6 pt-6">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold">Sign in</h1>
            <p className="text-sm text-muted-foreground">
              Your jobs, candidates and scores, in one place.
            </p>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <label className="block space-y-1.5 text-sm font-medium">
              Email
              <Input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="block space-y-1.5 text-sm font-medium">
              Password
              <Input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {login.isError && (
              <p role="alert" className="text-sm text-destructive">
                {login.error.message}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Signing in…' : 'Sign in'}
              {!login.isPending && <ArrowRight aria-hidden />}
            </Button>
          </form>
          {demo.data && (
            <div className="space-y-3 border-t pt-5">
              <Button
                type="button"
                variant="outline"
                className="w-full"
                disabled={login.isPending}
                onClick={() => signIn(demo.data!)}
              >
                <Sparkles aria-hidden />
                Use the demo account
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                {demo.data.email} · {demo.data.password}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
