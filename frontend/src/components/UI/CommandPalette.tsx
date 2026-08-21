import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface Command {
  id: string;
  label: string;
  section: string;
  icon?: ReactNode;
  shortcut?: string;
  run: () => void;
}

interface CommandPaletteProps {
  commands: Command[];
}

/**
 * CommandPalette — the keyboard-first entry point into every real action
 * Genie can perform. Opens with Ctrl/Cmd+K. Every entry maps to a genuine
 * app action; there is no placeholder search over fake data.
 */
export function CommandPalette({ commands }: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelected(0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q) || c.section.toLowerCase().includes(q));
  }, [commands, query]);

  const runSelected = (cmd: Command) => {
    cmd.run();
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="command-palette-backdrop flex items-start justify-center pt-[16vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16 }}
          onClick={() => setOpen(false)}
        >
          <motion.div
            className="command-palette"
            initial={{ opacity: 0, scale: 0.97, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            onClick={(e) => e.stopPropagation()}
          >
            <input
              autoFocus
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelected(0);
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault();
                  setSelected((i) => Math.min(i + 1, filtered.length - 1));
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault();
                  setSelected((i) => Math.max(i - 1, 0));
                } else if (e.key === 'Enter' && filtered[selected]) {
                  e.preventDefault();
                  runSelected(filtered[selected]);
                }
              }}
              placeholder="Ask Genie or run a command…"
            />
            <div className="max-h-80 overflow-y-auto custom-scrollbar py-1.5">
              {filtered.length === 0 ? (
                <div className="px-5 py-6 text-center text-xs text-[color:var(--text-faint)]">No matching commands.</div>
              ) : (
                filtered.map((cmd, i) => (
                  <button
                    key={cmd.id}
                    className={`command-palette-item ${i === selected ? 'is-selected' : ''}`}
                    onMouseEnter={() => setSelected(i)}
                    onClick={() => runSelected(cmd)}
                  >
                    {cmd.icon}
                    <span className="flex-1">{cmd.label}</span>
                    <span className="text-[10px] uppercase tracking-wide text-[color:var(--text-faint)]">{cmd.section}</span>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
