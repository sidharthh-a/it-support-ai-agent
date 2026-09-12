import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Bot, Ticket, BookOpen, BarChart3, Settings as SettingsIcon, Sun, Moon, LogOut, Menu, X, ShieldCheck } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

const NAV_ITEMS = [
  { to: '/chat', label: 'AI Assistant', icon: Bot },
  { to: '/tickets', label: 'Tickets', icon: Ticket },
  { to: '/knowledge', label: 'Knowledge', icon: BookOpen },
  { to: '/analytics', label: 'Dashboard', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
];

const ROLE_BADGE: Record<string, { label: string; className: string }> = {
  admin: { label: 'Admin', className: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300' },
  support: { label: 'Support', className: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300' },
  employee: { label: 'Employee', className: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300' },
};

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout, isStaff, isAdmin } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  return (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 text-white shadow-md shadow-brand-500/25">
          <Bot className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">IT Support AI</p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">Grounded Agent Platform</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3" aria-label="Primary">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-100'
              }`
            }
          >
            <Icon className="h-4.5 w-4.5 h-[18px] w-[18px]" />
            {label}
            {to === '/analytics' && !isAdmin && !isStaff && <span className="ml-auto text-[10px] text-slate-400">view</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer / user */}
      <div className="border-t border-slate-200 p-3 dark:border-slate-800">
        <button
          onClick={toggleTheme}
          className="mb-2 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/60"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
        <div className="flex items-center gap-3 rounded-xl px-3 py-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600 dark:bg-slate-700 dark:text-slate-200">
            {user?.full_name?.split(' ').map((n) => n[0]).slice(0, 2).join('') || '?'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{user?.full_name}</p>
            <span className={`inline-block rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${ROLE_BADGE[user?.role || 'employee']?.className}`}>
              {ROLE_BADGE[user?.role || 'employee']?.label}
            </span>
          </div>
          <button
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
            aria-label="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export const AppLayout: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block dark:border-slate-800 dark:bg-slate-900/60">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 28, stiffness: 300 }}
              className="fixed inset-y-0 left-0 z-50 w-64 border-r border-slate-200 bg-white lg:hidden dark:border-slate-800 dark:bg-slate-900"
            >
              <button
                className="absolute right-3 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
              <SidebarContent onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur lg:hidden dark:border-slate-800 dark:bg-slate-900/70">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold">IT Support AI</span>
          <ShieldCheck className="ml-auto h-4 w-4 text-emerald-500" aria-label="Grounded mode" />
        </header>
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
