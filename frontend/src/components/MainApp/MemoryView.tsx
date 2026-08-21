/**
 * MemoryView.tsx — Memory UI inside Main Application.
 */
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BrainIcon,
  TrashIcon,
  PlusIcon,
  SparklesIcon,
} from '../UI/Icons';

interface MemoryItem {
  id: string;
  content: string;
  category: string;
  importance: number;
  created_at: number;
}

export default function MemoryView() {
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [memories, setMemories] = useState<MemoryItem[]>([
    { id: '1', content: 'User prefers Cyber Luxe dark glass theme for high contrast visual excellence.', category: 'Personal Preference', importance: 0.95, created_at: Date.now() - 3600000 },
    { id: '2', content: 'Project Genie AI: Screen companion mode floating draggable transparent overlay window.', category: 'Projects', importance: 0.9, created_at: Date.now() - 7200000 },
    { id: '3', content: 'Use sentence-transformers embeddings for local semantic memory vector retrieval.', category: 'Learned Preferences', importance: 0.85, created_at: Date.now() - 86400000 },
  ]);

  const categories = ['all', 'Personal Preference', 'Projects', 'Conversations', 'Tasks', 'Learned Preferences'];

  useEffect(() => {
    let isMounted = true;
    async function fetchMemories() {
      try {
        const res = await fetch(`/api/v1/memory/search?q=${encodeURIComponent(query)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.results && isMounted) {
            setMemories(data.results.map((r: any) => ({
              id: r.id || String(Math.random()),
              content: r.content || r.text || '',
              category: r.category || 'Conversations',
              importance: r.importance || 0.5,
              created_at: r.created_at || Date.now(),
            })));
          }
        }
      } catch {
        /* fallback to initial state */
      }
    }

    const timer = setTimeout(fetchMemories, 300);
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [query]);

  const handleDelete = (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const filteredMemories = memories.filter(
    (m) => activeCategory === 'all' || m.category.toLowerCase() === activeCategory.toLowerCase()
  );

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Genie AI Semantic Memory
          </h1>
          <p className="text-xs md:text-sm font-medium text-slate-400 mt-1">
            Long-term memory stored locally via sentence-transformers embeddings & SQLite.
          </p>
        </div>

        <button
          onClick={() => setMemories([])}
          className="px-4 py-2 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-bold hover:bg-rose-500/20 transition-all flex items-center gap-2"
        >
          <TrashIcon size={16} />
          <span>Clear Memory</span>
        </button>
      </div>

      {/* Search & Category Filter */}
      <div className="cyber-glass rounded-3xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full md:w-96 px-4 py-2.5 rounded-2xl bg-slate-900/80 border border-cyan-500/30 shadow-inner">
          <BrainIcon size={18} className="text-cyan-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search memory semantically…"
            className="w-full bg-transparent outline-none text-xs font-medium text-slate-200 placeholder:text-slate-500"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto custom-scrollbar">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3.5 py-2 rounded-2xl text-xs font-semibold capitalize whitespace-nowrap transition-all ${
                activeCategory === cat
                  ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/30'
                  : 'bg-white/5 text-slate-300 hover:bg-white/10 border border-white/10'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Memory List */}
      <div className="space-y-3">
        {filteredMemories.length === 0 ? (
          <div className="cyber-card rounded-3xl p-12 text-center text-slate-400 text-xs font-medium">
            No memories match your query. Talk to Genie or ask Genie to "remember" something!
          </div>
        ) : (
          filteredMemories.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="cyber-card rounded-3xl p-5 flex items-center justify-between gap-4 hover:border-cyan-500/40 transition-all"
            >
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="px-3 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-[10px] font-bold text-cyan-400 uppercase">
                    {m.category}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">
                    Importance: {Math.round(m.importance * 100)}%
                  </span>
                </div>
                <p className="text-xs font-semibold text-slate-200 leading-relaxed">{m.content}</p>
              </div>

              <button
                onClick={() => handleDelete(m.id)}
                className="p-2.5 rounded-2xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                title="Delete memory"
              >
                <TrashIcon size={16} />
              </button>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
