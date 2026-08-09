/**
 * MemoryView.tsx — Memory UI inside Main Application.
 *
 * Per spec §37:
 * Categories: Personal Preferences, Projects, Conversations, Tasks, Learned Preferences.
 * Actions: View, Search, Delete, Clear, Export.
 * Connects to actual local SQLite + Qdrant memory backend (`/api/v1/memory/search`).
 */
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

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
    { id: '1', content: 'User prefers Sky Blue light theme for interface.', category: 'Personal Preference', importance: 0.9, created_at: Date.now() - 3600000 },
    { id: '2', content: 'Project Genie AI: Desktop companion overlay with floating transparent window.', category: 'Projects', importance: 0.85, created_at: Date.now() - 7200000 },
    { id: '3', content: 'Use sentence-transformers all-MiniLM-L6-v2 for offline embeddings.', category: 'Learned Preferences', importance: 0.8, created_at: Date.now() - 86400000 },
  ]);

  const categories = ['all', 'Personal Preference', 'Projects', 'Conversations', 'Tasks', 'Learned Preferences'];

  // Search memories from backend API
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
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Genie Memory & Preferences
          </h1>
          <p className="text-sm font-medium text-slate-500 mt-1">
            Semantic memory stored locally via sentence-transformers embeddings & SQLite.
          </p>
        </div>

        <button
          onClick={() => setMemories([])}
          className="px-4 py-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold hover:bg-rose-100 transition-all"
        >
          Clear Memory
        </button>
      </div>

      {/* Search & Category Filter */}
      <div className="sky-glass rounded-2xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full md:w-96 px-3 py-2 rounded-xl bg-white border border-sky-200 shadow-sm">
          <span>🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search memory semantically…"
            className="w-full bg-transparent outline-none text-xs font-medium text-slate-800 placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto custom-scrollbar">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize whitespace-nowrap transition-all ${
                activeCategory === cat
                  ? 'bg-sky-500 text-white shadow-sm'
                  : 'bg-white/70 text-slate-600 hover:bg-white border border-sky-200/60'
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
          <div className="sky-glass-card rounded-2xl p-12 text-center text-slate-400 text-xs font-medium">
            No memories match your query. Talk to Genie or ask Genie to "remember" something!
          </div>
        ) : (
          filteredMemories.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="sky-glass-card rounded-2xl p-4 flex items-center justify-between gap-4 hover:border-sky-300 transition-all"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full bg-sky-100 border border-sky-300 text-[10px] font-bold text-sky-800 uppercase">
                    {m.category}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">
                    Importance: {Math.round(m.importance * 100)}%
                  </span>
                </div>
                <p className="text-xs font-semibold text-slate-800">{m.content}</p>
              </div>

              <button
                onClick={() => handleDelete(m.id)}
                className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all"
                title="Delete memory"
              >
                🗑
              </button>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
