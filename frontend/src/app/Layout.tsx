import { NavLink, Outlet, useLocation } from 'react-router'

import { Logo } from '@/components/brand/logo'
import { HealthBadge } from '@/features/health/HealthBadge'
import { cn } from '@/lib/utils'

import { ErrorBoundary } from './ErrorBoundary'

const NAV: { to: string; label: string; alsoActiveOn?: string }[] = [
  { to: '/', label: 'Score' },
  // A past run is opened from History, so History stays highlighted there.
  { to: '/history', label: 'History', alsoActiveOn: '/runs/' },
]

export function Layout() {
  const { pathname } = useLocation()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:gap-6">
          <NavLink to="/" aria-label="Home" className="shrink-0">
            <Logo />
          </NavLink>
          <nav className="flex gap-1 text-sm">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-2 py-1 text-muted-foreground transition-colors hover:text-foreground',
                    (isActive || (item.alsoActiveOn && pathname.startsWith(item.alsoActiveOn))) &&
                      'bg-accent font-medium text-accent-foreground hover:text-accent-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto shrink-0">
            <HealthBadge />
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
