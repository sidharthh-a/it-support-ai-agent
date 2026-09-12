import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bot, Mail, Lock, User as UserIcon, Loader2, ShieldCheck, Sparkles } from 'lucide-react';
import { ApiError } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname?: string } } };

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        const { api } = await import('../services/api');
        await api.register({ email, password, full_name: fullName, role: 'employee', department: 'General' });
        await login(email, password);
      }
      navigate(location.state?.from?.pathname || '/chat', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const inputClass =
    'w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder-slate-500';

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-gradient-to-br from-slate-50 via-white to-brand-50 px-4 dark:from-slate-950 dark:via-slate-950 dark:to-slate-900">
      <div className="w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl shadow-slate-200/60 lg:grid lg:grid-cols-2 dark:border-slate-800 dark:bg-slate-900 dark:shadow-black/40">
        {/* Left: brand panel */}
        <div className="relative hidden flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-600 to-indigo-600 p-10 text-white lg:flex">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 backdrop-blur">
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <p className="text-lg font-bold">IT Support AI</p>
                <p className="text-xs text-white/70">Enterprise Support Platform</p>
              </div>
            </div>
            <h1 className="mt-14 text-3xl font-bold leading-snug">
              Grounded answers.
              <br />
              Zero hallucinations.
            </h1>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/75">
              Every response is synthesized strictly from your knowledge base (pgvector RAG), ticket history and
              system logs — with citations you can verify.
            </p>
          </div>
          <ul className="space-y-3 text-sm text-white/85">
            <li className="flex items-center gap-2.5"><Sparkles className="h-4 w-4 text-amber-300" /> Streaming grounded responses</li>
            <li className="flex items-center gap-2.5"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Deterministic safety overrides</li>
            <li className="flex items-center gap-2.5"><Bot className="h-4 w-4 text-white/70" /> 6 audited agent tools</li>
          </ul>
        </div>

        {/* Right: form */}
        <div className="p-8 sm:p-12">
          <div className="mx-auto max-w-sm">
            <div className="mb-8 flex items-center gap-2.5 lg:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
                <Bot className="h-5 w-5" />
              </div>
              <p className="text-lg font-bold text-slate-900 dark:text-white">IT Support AI</p>
            </div>

            <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
              {mode === 'login' ? 'Sign in to your workspace.' : 'The first account becomes the workspace admin.'}
            </p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              {mode === 'register' && (
                <div className="relative">
                  <UserIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input className={inputClass} placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} autoComplete="name" />
                </div>
              )}
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input className={inputClass} type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input className={inputClass} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
              </div>

              {error && (
                <div role="alert" className="rounded-xl bg-red-50 px-3.5 py-2.5 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand-500/25 transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
              {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
              <button
                type="button"
                onClick={() => {
                  setMode(mode === 'login' ? 'register' : 'login');
                  setError(null);
                }}
                className="font-semibold text-brand-600 hover:text-brand-500 dark:text-brand-400"
              >
                {mode === 'login' ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
