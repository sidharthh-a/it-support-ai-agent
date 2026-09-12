import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { TicketCheck, Timer, BookOpen, TrendingUp, AlertOctagon } from 'lucide-react';
import { api, AnalyticsDashboard } from '../services/api';
import { Spinner } from '../components/ui/Spinner';

const PRIORITY_COLORS: Record<string, string> = {
  low: '#94a3b8',
  medium: '#38bdf8',
  high: '#fb923c',
  critical: '#ef4444',
};

const PIE_COLORS = ['#3d6def', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'];
const label = (s: string) => s.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const ChartCard: React.FC<{ title: string; subtitle?: string; children: React.ReactNode; className?: string }> = ({ title, subtitle, children, className = '' }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/50 ${className}`}>
    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">{title}</h3>
    {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
    <div className="mt-4 h-64">{children}</div>
  </div>
);

const KpiCard: React.FC<{ icon: React.ReactNode; label: string; value: string; accent: string }> = ({ icon, label, value, accent }) => (
  <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/50">
    <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${accent}`}>{icon}</div>
    <div>
      <p className="text-xs font-medium text-slate-400">{label}</p>
      <p className="text-xl font-bold text-slate-900 dark:text-white">{value}</p>
    </div>
  </div>
);

const tooltipStyle = {
  backgroundColor: 'rgba(15,23,42,0.92)',
  border: 'none',
  borderRadius: '0.75rem',
  color: '#e2e8f0',
  fontSize: '12px',
};

export const AnalyticsPage: React.FC = () => {
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAnalyticsDashboard(30)
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="rounded-2xl bg-red-50 px-6 py-4 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">{error}</div>
      </div>
    );
  }
  if (!data) {
    return <div className="flex h-full items-center justify-center"><Spinner size="lg" /></div>;
  }

  const s = data.summary;
  const trendData = data.daily_trend.map((d) => ({ ...d, label: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }));

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Service Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">All metrics aggregated live from the database (last 30 days trend window)</p>
        </div>

        {/* KPI row */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard icon={<TicketCheck className="h-5 w-5 text-emerald-500" />} label="Resolution rate" value={`${s.ai_resolution_rate}%`} accent="bg-emerald-500/10" />
          <KpiCard icon={<Timer className="h-5 w-5 text-brand-500" />} label="Avg resolution time" value={`${data.avg_resolution_time_hours}h`} accent="bg-brand-500/10" />
          <KpiCard icon={<BookOpen className="h-5 w-5 text-violet-500" />} label="Knowledge docs" value={String(s.total_knowledge_docs)} accent="bg-violet-500/10" />
          <KpiCard icon={<TrendingUp className="h-5 w-5 text-amber-500" />} label="Total tickets" value={String(s.total_tickets)} accent="bg-amber-500/10" />
        </div>

        {/* Charts row 1 */}
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Daily ticket trend" subtitle="Tickets created per day">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3d6def" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3d6def" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" minTickGap={28} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="count" name="Tickets" stroke="#3d6def" strokeWidth={2} fill="url(#trendFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Tickets by priority">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.tickets_by_priority} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
                <XAxis dataKey="priority" tick={{ fontSize: 11 }} tickFormatter={label} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(100,116,139,0.08)' }} />
                <Bar dataKey="count" name="Tickets" radius={[6, 6, 0, 0]}>
                  {data.tickets_by_priority.map((entry) => (
                    <Cell key={entry.priority} fill={PRIORITY_COLORS[entry.priority] || '#3d6def'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Charts row 2 */}
        <div className="grid gap-4 lg:grid-cols-3">
          <ChartCard title="Incidents by category" subtitle="Ticket volume per category">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.tickets_by_category} dataKey="count" nameKey="category" innerRadius={52} outerRadius={85} paddingAngle={3} strokeWidth={0}>
                  {data.tickets_by_category.map((entry, i) => (
                    <Cell key={entry.category} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v: string) => label(v)} />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Top recurring errors" subtitle="Most frequent error codes in system logs">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.top_recurring_errors} layout="vertical" margin={{ top: 0, right: 12, left: 30, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                <YAxis type="category" dataKey="error_code" width={140} tick={{ fontSize: 9, fontFamily: 'monospace' }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(100,116,139,0.08)' }} />
                <Bar dataKey="count" name="Occurrences" fill="#f59e0b" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Resolution rate by category">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.resolution_rate_by_category} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
                <XAxis dataKey="category" tick={{ fontSize: 10 }} tickFormatter={label} interval={0} angle={-14} dy={8} height={44} />
                <YAxis tick={{ fontSize: 10 }} unit="%" />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(100,116,139,0.08)' }} />
                <Bar dataKey="rate" name="Resolved %" fill="#10b981" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Knowledge usage strip */}
        <div className="grid gap-4 sm:grid-cols-4">
          <KpiCard icon={<BookOpen className="h-5 w-5 text-brand-500" />} label="Documents" value={String(data.knowledge_usage.total_documents)} accent="bg-brand-500/10" />
          <KpiCard icon={<BookOpen className="h-5 w-5 text-violet-500" />} label="Chunks indexed" value={String(data.knowledge_usage.total_chunks)} accent="bg-violet-500/10" />
          <KpiCard icon={<BookOpen className="h-5 w-5 text-emerald-500" />} label="Embedded chunks" value={String(data.knowledge_usage.embedded_chunks)} accent="bg-emerald-500/10" />
          <KpiCard icon={<AlertOctagon className="h-5 w-5 text-amber-500" />} label="Embedding coverage" value={`${data.knowledge_usage.embedding_coverage}%`} accent="bg-amber-500/10" />
        </div>
      </div>
    </div>
  );
};
