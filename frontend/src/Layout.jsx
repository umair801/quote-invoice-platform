import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/configurator', label: 'New Quote' },
  { to: '/quotes',       label: 'Quotes' },
  { to: '/orders',       label: 'Orders' },
]

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-offwhite">
      {/* ─── Top nav ──────────────────────────────────────────────────────── */}
      <header className="bg-navy text-offwhite shadow-md">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gold rounded-sm flex items-center justify-center font-bold text-navy text-sm">
              SF
            </div>
            <span className="font-semibold text-lg tracking-wide">
              Skyframe Studio
            </span>
          </div>

          <nav className="flex items-center gap-1">
            {navItems.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `px-4 py-2 rounded text-sm font-medium transition-colors duration-150 ${
                    isActive
                      ? 'bg-gold text-navy'
                      : 'text-offwhite hover:bg-white/10'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {/* ─── Page content ─────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        <Outlet />
      </main>

      {/* ─── Footer ───────────────────────────────────────────────────────── */}
      <footer className="bg-navy text-muted text-xs text-center py-3">
        Custom Framing Management Platform
      </footer>
    </div>
  )
}
