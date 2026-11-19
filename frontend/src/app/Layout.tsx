import { LogOut } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { Logo } from '@/components/brand/logo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useLogout, useMe } from '@/features/auth/api'
import { HealthBadge } from '@/features/health/HealthBadge'
import { cn } from '@/lib/utils'

import { ErrorBoundary } from './ErrorBoundary'

const NAV: { to: string; label: string }[] = [
  { to: '/jobs', label: 'Jobs' },
  { to: '/search', label: 'Search' },
]

function UserMenu() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  if (!me.data) return null
  return (
    <div className="flex items-center gap-2">
      <span className="hidden min-w-0 text-sm text-muted-foreground sm:block">
        <span className="truncate">{me.data.name}</span>
      </span>
      {me.data.is_demo && <Badge tone="accent">Demo</Badge>}
      <Button
        variant="ghost"
        size="icon"
        aria-label="Sign out"
        title="Sign out"
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}
      >
        <LogOut aria-hidden />
      </Button>
    </div>
  )
}

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:gap-6">
          <NavLink to="/jobs" aria-label="Home" className="shrink-0">
            <span className="hidden sm:inline">
              <Logo />
            </span>
            <span className="sm:hidden">
              <Logo showName={false} />
            </span>
          </NavLink>
          <nav className="flex gap-1 text-sm">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-2 py-1 text-muted-foreground transition-colors hover:text-foreground',
                    isActive &&
                      'bg-accent font-medium text-accent-foreground hover:text-accent-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <HealthBadge />
            <UserMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        {/* Per-page boundary: a crash in one page keeps the header usable. */}
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  )
}
