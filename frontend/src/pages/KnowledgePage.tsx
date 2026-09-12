import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Upload, FileText, Trash2, RefreshCw, Search, Eye, X, Loader2, BookOpen, FileJson, FileCode,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { api, KnowledgeDocument, KnowledgePreview, SearchResult, ApiError } from '../services/api';
import { Spinner } from '../components/ui/Spinner';
import { useAuth } from '../context/AuthContext';

const CATEGORY_COLORS: Record<string, string> = {
  Network: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  Access: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  Software: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  Hardware: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  Security: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  General: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300',
};

function fileIcon(type: string) {
  if (type === 'pdf') return <FileText className="h-4 w-4" />;
  if (type === 'json') return <FileJson className="h-4 w-4" />;
  return <FileCode className="h-4 w-4" />;
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const tokens = query.trim().split(/\s+/).filter((t) => t.length > 1).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!tokens.length) return <>{text}</>;
  const regex = new RegExp(`(${tokens.join('|')})`, 'gi');
  const parts = text.split(regex);
  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) && tokens.some((t) => new RegExp(`^${t}$`, 'i').test(part)) ? (
          <mark key={i} className="rounded bg-amber-200/70 px-0.5 text-inherit dark:bg-amber-500/30 dark:text-amber-100">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

export const KnowledgePage: React.FC = () => {
  const { isStaff } = useAuth();
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [preview, setPreview] = useState<KnowledgePreview | null>(null);
  const [reindexing, setReindexing] = useState<number | null>(null);

  // Upload form state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('General');
  const [pasteContent, setPasteContent] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocs = useCallback(async () => {
    setLoading(true);
    try {
      setDocs(await api.getKnowledgeDocs());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    try {
      setSearchResults(await api.searchKnowledge(searchQuery, 8));
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadError(null);
    setUploading(true);
    try {
      if (file) {
        await api.uploadKnowledgeFile(title, category, file);
      } else {
        await api.uploadKnowledgeDoc({ title, category, content: pasteContent, file_type: 'markdown' });
      }
      setUploadOpen(false);
      setTitle('');
      setPasteContent('');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadDocs();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteKnowledgeDoc(id);
    await loadDocs();
  };

  const handleReindex = async (id: number) => {
    setReindexing(id);
    try {
      await api.reindexKnowledgeDoc(id);
      await loadDocs();
    } finally {
      setReindexing(null);
    }
  };

  const openPreview = async (id: number) => {
    setPreview(await api.previewKnowledgeDoc(id));
  };

  const inputClass =
    'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Knowledge Base</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {docs.length} document{docs.length !== 1 ? 's' : ''} indexed for grounded retrieval
            </p>
          </div>
          {isStaff && (
            <button
              onClick={() => setUploadOpen(true)}
              className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand-500/20 transition hover:bg-brand-500"
            >
              <Upload className="h-4 w-4" /> Upload document
            </button>
          )}
        </div>

        {/* Semantic search */}
        <form onSubmit={handleSearch} className="mt-6 flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Semantic search across all knowledge chunks…"
              className={`${inputClass} pl-10`}
            />
          </div>
          <button
            type="submit"
            disabled={searching}
            className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
          >
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
          </button>
          {searchResults && (
            <button type="button" onClick={() => { setSearchResults(null); setSearchQuery(''); }} className="rounded-xl border border-slate-200 px-3 text-sm text-slate-500 dark:border-slate-700">
              Clear
            </button>
          )}
        </form>

        {/* Search results with highlighting */}
        {searchResults && (
          <div className="mt-5 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{searchResults.length} matching chunks</p>
            {searchResults.map((r) => (
              <div key={r.chunk_id} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700/60 dark:bg-slate-800/50">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{r.title}</p>
                  <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                    {r.score > 0 ? `${(r.score * 100).toFixed(0)}% match` : r.search_type || 'keyword'}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                  <HighlightedText text={r.content.slice(0, 400)} query={searchQuery} />
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Document list */}
        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {docs.map((doc) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-brand-300 hover:shadow-lg hover:shadow-brand-500/5 dark:border-slate-700/60 dark:bg-slate-800/50 dark:hover:border-brand-500/40"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500/10 text-brand-600 dark:text-brand-300">
                    {fileIcon(doc.file_type)}
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${CATEGORY_COLORS[doc.category] || CATEGORY_COLORS.General}`}>
                    {doc.category}
                  </span>
                </div>
                <p className="mt-3 line-clamp-2 text-sm font-semibold text-slate-800 dark:text-slate-100">{doc.title}</p>
                <p className="mt-1 text-[11px] text-slate-400">
                  {doc.chunks.length} chunks · {new Date(doc.created_at).toLocaleDateString()} · {doc.file_type.toUpperCase()}
                </p>
                <div className="mt-4 flex items-center gap-1 border-t border-slate-100 pt-3 dark:border-slate-700/50">
                  <button onClick={() => openPreview(doc.id)} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700/60" title="Preview">
                    <Eye className="h-3.5 w-3.5" /> Preview
                  </button>
                  {isStaff && (
                    <>
                      <button onClick={() => handleReindex(doc.id)} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50 dark:hover:bg-slate-700/60" disabled={reindexing === doc.id} title="Re-embed chunks">
                        {reindexing === doc.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Reindex
                      </button>
                      <button onClick={() => handleDelete(doc.id)} className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-red-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10" title="Delete">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </motion.div>
            ))}
            {docs.length === 0 && (
              <div className="col-span-full flex flex-col items-center py-16 text-center">
                <BookOpen className="h-10 w-10 text-slate-300 dark:text-slate-600" />
                <p className="mt-3 text-sm text-slate-400">No documents yet. Upload your first guide to ground the assistant.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload modal */}
      <AnimatePresence>
        {uploadOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onClick={() => setUploadOpen(false)}>
            <motion.form
              initial={{ scale: 0.95, y: 12 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              onSubmit={handleUpload}
              className="w-full max-w-lg space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Upload knowledge document</h3>
                <button type="button" onClick={() => setUploadOpen(false)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-5 w-5" /></button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Title</label>
                  <input value={title} onChange={(e) => setTitle(e.target.value)} required className={inputClass} placeholder="VPN Troubleshooting Guide" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputClass}>
                    {Object.keys(CATEGORY_COLORS).map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">File (PDF, TXT, MD, JSON — max 10 MB)</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,.markdown,.json"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] || null);
                    if (e.target.files?.[0] && !title) setTitle(e.target.files[0].name.replace(/\.[^.]+$/, ''));
                  }}
                  className="w-full rounded-xl border border-dashed border-slate-300 px-3 py-2.5 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-brand-600 dark:border-slate-600 dark:file:bg-brand-500/10 dark:file:text-brand-300"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">…or paste content directly</label>
                <textarea value={pasteContent} onChange={(e) => setPasteContent(e.target.value)} rows={5} className={inputClass} placeholder="# Guide title&#10;1. Step one…&#10;2. Step two…" disabled={!!file} />
              </div>
              {uploadError && <div className="rounded-xl bg-red-50 px-3.5 py-2.5 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">{uploadError}</div>}
              <button type="submit" disabled={uploading || (!file && !pasteContent.trim())} className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-60">
                {uploading && <Loader2 className="h-4 w-4 animate-spin" />} Ingest & embed
              </button>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Preview modal */}
      <AnimatePresence>
        {preview && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onClick={() => setPreview(null)}>
            <motion.div
              initial={{ scale: 0.95, y: 12 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between border-b border-slate-200 p-5 dark:border-slate-700">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">{preview.title}</h3>
                  <p className="text-xs text-slate-400">{preview.category} · {preview.chunk_count} chunks · {preview.file_type.toUpperCase()}</p>
                </div>
                <button onClick={() => setPreview(null)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-5 w-5" /></button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                  <HighlightedText text={preview.content} query={searchQuery} />
                </pre>
                {preview.truncated && <p className="mt-3 text-xs italic text-slate-400">Preview truncated…</p>}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
