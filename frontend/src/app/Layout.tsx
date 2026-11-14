import { NavLink, Outlet } from 'react-router'

import { uiConfig } from '@/config/ui'
import { HealthBadge } from '@/features/health/HealthBadge'
import { cn } from '@/lib/utils'

import { ErrorBoundary } from './ErrorBoundary'

const NAV = [
  { to: '/', label: 'Score' },
  // Phase 3 adds: { to: '/runs', label: 'Runs' }, { to: '/costs', label: 'Costs' }
] as const

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <span className="font-semibold">{uiConfig.appName}</span>
          <nav className="flex gap-4 text-sm">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  cn('text-muted-foreground hover:text-foreground', isActive && 'text-foreground')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <HealthBadge />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {/* Per-page boundary: a crash in one page keeps the header usable. */}
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  )
}
