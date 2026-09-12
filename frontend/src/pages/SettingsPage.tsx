import React, { useCallback, useEffect, useState } from 'react';
import {
  Sun, Moon, KeyRound, Loader2, Check, ShieldCheck, Server, Users, ScrollText,
  RefreshCcw, Database, Cpu, X,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { api, SystemInfo, UserProfile, AdminLog, ApiError } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { Spinner } from '../components/ui/Spinner';

const ROLE_STYLE: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300',
  support: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  employee: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300',
};

function PasswordCard() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await api.changePassword(current, next);
      setMsg({ ok: true, text: 'Password updated successfully.' });
      setCurrent('');
      setNext('');
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : 'Change failed' });
    } finally {
      setBusy(false);
    }
  };

  const input = 'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

  return (
    <form onSubmit={submit} className="space-y-3">
      <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required placeholder="Current password" autoComplete="current-password" className={input} />
      <input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} placeholder="New password (min 8 characters)" autoComplete="new-password" className={input} />
      {msg && <p className={`text-sm ${msg.ok ? 'text-emerald-500' : 'text-red-500'}`}>{msg.text}</p>}
      <button type="submit" disabled={busy} className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-60">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />} Update password
      </button>
    </form>
  );
}

function AdminPanel() {
  const [tab, setTab] = useState<'system' | 'users' | 'logs'>('system');
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [logs, setLogs] = useState<AdminLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [reindexed, setReindexed] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'system') setSystem(await api.getSystemInfo());
      if (tab === 'users') setUsers(await api.getAdminUsers());
      if (tab === 'logs') setLogs(await api.getAdminLogs());
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const r = await api.reindexAll();
      setReindexed(`Re-embedded ${r.reindexed} chunks (${r.skipped} skipped) at ${r.dimension} dims.`);
      if (tab === 'system') await load();
    } finally {
      setReindexing(false);
    }
  };

  const handleRoleChange = async (id: number, role: string) => {
    await api.updateAdminUser(id, { role });
    await load();
  };

  const handleToggleActive = async (u: UserProfile) => {
    await api.updateAdminUser(u.id, { is_active: !u.is_active });
    await load();
  };

  const handleCreateUser = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    await api.createAdminUser({
      email: String(fd.get('email')),
      password: String(fd.get('password')),
      full_name: String(fd.get('full_name')),
      role: String(fd.get('role')),
      department: String(fd.get('department') || 'General'),
    });
    e.currentTarget.reset();
    await load();
  };

  const input = 'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700/60 dark:bg-slate-800/50">
      <div className="mb-5 flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-purple-500" />
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">Admin panel</h2>
        <div className="ml-auto flex gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-900">
          {(['system', 'users', 'logs'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold capitalize transition ${
                tab === t ? 'bg-white text-brand-600 shadow dark:bg-slate-800 dark:text-brand-300' : 'text-slate-500 hover:text-slate-700 dark:text-slate-400'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="flex justify-center py-10"><Spinner /></div>}

      {/* System */}
      {!loading && tab === 'system' && system && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3.5 dark:bg-slate-900/60">
              <Database className="h-5 w-5 text-emerald-500" />
              <div>
                <p className="text-xs text-slate-400">Database</p>
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {system.database.healthy ? 'Healthy' : 'Unreachable'} {system.database.latency_ms !== null && `· ${system.database.latency_ms} ms`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3.5 dark:bg-slate-900/60">
              <Cpu className="h-5 w-5 text-brand-500" />
              <div>
                <p className="text-xs text-slate-400">Embedding model</p>
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{system.embedding.model} · {system.embedding.dimension}d · {system.embedding.provider}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3.5 dark:bg-slate-900/60">
              <Server className="h-5 w-5 text-violet-500" />
              <div>
                <p className="text-xs text-slate-400">Gemini model</p>
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{system.llm.gemini_model} {system.llm.gemini_configured ? '' : '(fallback mode)'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3.5 dark:bg-slate-900/60">
              <ScrollText className="h-5 w-5 text-amber-500" />
              <div>
                <p className="text-xs text-slate-400">Vector store</p>
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {system.embedding.chunks} chunks · {system.embedding.embedding_coverage}% embedded
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleReindex} disabled={reindexing} className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-60">
              {reindexing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />} Reindex all embeddings
            </button>
            {reindexed && <p className="text-xs text-emerald-500">{reindexed}</p>}
          </div>
          <p className="text-[11px] text-slate-400">v{system.version} · {system.environment} · Python {system.python_version}</p>
        </div>
      )}

      {/* Users */}
      {!loading && tab === 'users' && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-400 dark:bg-slate-900/60">
                <tr><th className="px-4 py-2.5">User</th><th className="px-4 py-2.5">Role</th><th className="px-4 py-2.5">Status</th><th className="w-24" /></tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-slate-800 dark:text-slate-100">{u.full_name}</p>
                      <p className="text-[11px] text-slate-400">{u.email} · {u.department}</p>
                    </td>
                    <td className="px-4 py-2.5">
                      <select value={u.role} onChange={(e) => handleRoleChange(u.id, e.target.value)} className={`rounded-lg border-0 px-2 py-1 text-xs font-bold ${ROLE_STYLE[u.role]}`} aria-label={`Role for ${u.full_name}`}>
                        <option value="admin">Admin</option>
                        <option value="support">Support</option>
                        <option value="employee">Employee</option>
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-semibold ${u.is_active ? 'text-emerald-500' : 'text-red-400'}`}>{u.is_active ? 'Active' : 'Disabled'}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button onClick={() => handleToggleActive(u)} className="text-xs font-semibold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
                        {u.is_active ? 'Disable' : 'Enable'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form onSubmit={handleCreateUser} className="grid gap-2 sm:grid-cols-5">
            <input name="full_name" required placeholder="Full name" className={`${input} sm:col-span-2`} />
            <input name="email" type="email" required placeholder="email@company.com" className={input} />
            <input name="password" type="password" required minLength={8} placeholder="Password" className={input} />
            <div className="flex gap-2">
              <select name="role" className={input} aria-label="New user role" defaultValue="employee">
                <option value="employee">Employee</option>
                <option value="support">Support</option>
                <option value="admin">Admin</option>
              </select>
              <button type="submit" className="shrink-0 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-500" aria-label="Create user">Add</button>
            </div>
          </form>
        </div>
      )}

      {/* Logs */}
      {!loading && tab === 'logs' && (
        <div className="max-h-96 space-y-2 overflow-y-auto">
          {logs.map((l) => (
            <div key={l.id} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900/60">
              <p className="font-mono text-[11px] font-bold text-amber-600 dark:text-amber-400">{l.error_code} · {l.service_name}</p>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{l.log_message}</p>
              <p className="mt-0.5 text-[10px] text-slate-400">{new Date(l.timestamp).toLocaleString()}</p>
            </div>
          ))}
          {!logs.length && <p className="py-8 text-center text-sm text-slate-400">No system logs recorded.</p>}
        </div>
      )}
    </div>
  );
}

export const SettingsPage: React.FC = () => {
  const { user, isAdmin } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Settings</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Manage your account and workspace preferences.</p>
        </div>

        {/* Profile */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700/60 dark:bg-slate-800/50">
          <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">Profile</h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-xs text-slate-400">Name</dt><dd className="mt-0.5 font-medium text-slate-800 dark:text-slate-100">{user?.full_name}</dd></div>
            <div><dt className="text-xs text-slate-400">Email</dt><dd className="mt-0.5 font-medium text-slate-800 dark:text-slate-100">{user?.email}</dd></div>
            <div><dt className="text-xs text-slate-400">Role</dt><dd className="mt-0.5"><span className={`rounded-full px-2 py-0.5 text-xs font-bold ${ROLE_STYLE[user?.role || 'employee']}`}>{user?.role}</span></dd></div>
            <div><dt className="text-xs text-slate-400">Department</dt><dd className="mt-0.5 font-medium text-slate-800 dark:text-slate-100">{user?.department}</dd></div>
          </dl>
        </section>

        {/* Appearance */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700/60 dark:bg-slate-800/50">
          <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">Appearance</h2>
          <button onClick={toggleTheme} className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm transition hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40">
            {theme === 'dark' ? <Moon className="h-4 w-4 text-brand-400" /> : <Sun className="h-4 w-4 text-amber-500" />}
            <span className="font-medium text-slate-700 dark:text-slate-200">{theme === 'dark' ? 'Dark' : 'Light'} mode</span>
            <span className="ml-6 text-xs text-slate-400">Click to switch</span>
          </button>
        </section>

        {/* Security */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700/60 dark:bg-slate-800/50">
          <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">Security</h2>
          <PasswordCard />
        </section>

        {isAdmin && <AdminPanel />}
      </div>
    </div>
  );
};
