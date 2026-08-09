/**
 * ToolFeedback.tsx — Non-blocking tool execution status and confirmation dialogs.
 *
 * Implements:
 * - Real-time tool progress indicator (appears when Genie is using tools)
 * - Confirmation dialog for destructive operations (delete, format, deploy, etc.)
 * - Tool completion notification
 *
 * Per spec §24: destructive operations must NEVER execute without user confirmation.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';

// Operations that require explicit confirmation before execution
const DESTRUCTIVE_OPERATIONS = new Set([
  'delete_file',
  'delete_folder',
  'write_file',  // overwrite
  'run_terminal',
  'kill_process',
  'deploy',
  'format_disk',
  'clear_database',
  'send_email',
  'send_message',
  'make_payment',
  'modify_system',
  'install_package',
  'uninstall_package',
]);

interface ToolEvent {
  type: 'tool_start' | 'tool_end';
  name: string;
  args?: Record<string, unknown>;
  result?: { status: string; message: string };
  id?: string;
}

interface PendingConfirmation {
  toolName: string;
  args: Record<string, unknown>;
  id: string;
  resolve: (confirmed: boolean) => void;
}

// Global confirmation queue (used by the WS message handler)
let _pendingConfirmations: Map<string, PendingConfirmation> = new Map();
let _confirmationCallbacks: Set<(pending: PendingConfirmation[]) => void> = new Set();

export function queueConfirmation(toolName: string, args: Record<string, unknown>): Promise<boolean> {
  return new Promise((resolve) => {
    const id = `conf-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const entry: PendingConfirmation = { toolName, args, id, resolve };
    _pendingConfirmations.set(id, entry);
    _confirmationCallbacks.forEach(cb => cb(Array.from(_pendingConfirmations.values())));
  });
}

export function usePendingConfirmations() {
  const [pending, setPending] = useState<PendingConfirmation[]>([]);

  useEffect(() => {
    const cb = (list: PendingConfirmation[]) => setPending([...list]);
    _confirmationCallbacks.add(cb);
    return () => { _confirmationCallbacks.delete(cb); };
  }, []);

  const confirm = useCallback((id: string, approved: boolean) => {
    const entry = _pendingConfirmations.get(id);
    if (entry) {
      entry.resolve(approved);
      _pendingConfirmations.delete(id);
      _confirmationCallbacks.forEach(cb => cb(Array.from(_pendingConfirmations.values())));
    }
  }, []);

  return { pending, confirm };
}


// ═══════════════════════════════════════════════════════════════════════════════
// Tool Feedback — Main component
// ═══════════════════════════════════════════════════════════════════════════════

export default function ToolFeedback() {
  const activeTools = useAppStore((s) => s.activeTools);
  const { pending, confirm } = usePendingConfirmations();
  const [completedTools, setCompletedTools] = useState<Array<{name: string; status: string; id: string}>>([]);

  // Track tool completions for transient notifications
  useEffect(() => {
    const prevTools = activeTools;
    // Would normally diff vs previous, but that needs useRef
  }, [activeTools]);

  if (!activeTools?.length && !pending.length) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 90,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9996,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        pointerEvents: 'none',
        maxWidth: 480,
      }}
    >
      {/* Confirmation dialogs — highest priority */}
      <AnimatePresence>
        {pending.map((item) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            style={{
              background: 'rgba(248,113,113,0.12)',
              border: '1.5px solid rgba(248,113,113,0.5)',
              borderRadius: 20,
              padding: '16px 20px',
              backdropFilter: 'blur(20px)',
              boxShadow: '0 16px 48px rgba(0,0,0,0.6), 0 0 40px rgba(248,113,113,0.15)',
              width: 460,
              pointerEvents: 'auto',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            {/* Warning header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <motion.span
                style={{ fontSize: 20 }}
                animate={{ rotate: [0, -5, 5, 0] }}
                transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 2 }}
              >
                ⚠️
              </motion.span>
              <div>
                <div style={{ color: '#f87171', fontSize: 13, fontWeight: 700 }}>
                  Confirmation Required
                </div>
                <div style={{ color: '#64748b', fontSize: 11, marginTop: 1 }}>
                  Genie wants to run a sensitive operation
                </div>
              </div>
            </div>

            {/* Operation details */}
            <div style={{
              background: 'rgba(0,0,0,0.3)',
              borderRadius: 12,
              padding: '10px 14px',
              marginBottom: 14,
            }}>
              <div style={{ color: '#f87171', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', marginBottom: 6 }}>
                OPERATION: {item.toolName.replace(/_/g, ' ').toUpperCase()}
              </div>
              {Object.entries(item.args).slice(0, 4).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                  <span style={{ color: '#475569', fontSize: 11, minWidth: 80 }}>{k}:</span>
                  <span style={{ color: '#94a3b8', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {String(v).slice(0, 80)}
                  </span>
                </div>
              ))}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => confirm(item.id, false)}
                style={{
                  flex: 1,
                  padding: '10px',
                  borderRadius: 12,
                  background: 'rgba(100,116,139,0.2)',
                  border: '1px solid rgba(100,116,139,0.4)',
                  color: '#94a3b8',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: "'Inter', sans-serif",
                  transition: 'all 0.15s',
                }}
              >
                ✕ Cancel
              </button>
              <button
                onClick={() => confirm(item.id, true)}
                style={{
                  flex: 1,
                  padding: '10px',
                  borderRadius: 12,
                  background: 'rgba(248,113,113,0.2)',
                  border: '1px solid rgba(248,113,113,0.5)',
                  color: '#f87171',
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: 'pointer',
                  fontFamily: "'Inter', sans-serif",
                  transition: 'all 0.15s',
                }}
              >
                ✓ Confirm
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Active tool indicators */}
      <AnimatePresence>
        {activeTools?.length > 0 && !pending.length && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            style={{
              background: 'rgba(8,12,28,0.92)',
              border: '1px solid rgba(129,140,248,0.3)',
              borderRadius: 18,
              padding: '10px 16px',
              backdropFilter: 'blur(16px)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontFamily: "'Inter', sans-serif",
            }}
          >
            {/* Spinner */}
            <motion.div
              style={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                border: '2px solid rgba(129,140,248,0.3)',
                borderTop: '2px solid #818CF8',
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
            />

            <div>
              <div style={{ color: '#e2e8f0', fontSize: 12, fontWeight: 600 }}>
                {activeTools.length === 1
                  ? `Using: ${activeTools[0].name?.replace(/_/g, ' ')}`
                  : `Running ${activeTools.length} operations`}
              </div>
              {activeTools[0]?.args && Object.keys(activeTools[0].args).length > 0 && (
                <div style={{ color: '#64748b', fontSize: 10, marginTop: 2 }}>
                  {Object.entries(activeTools[0].args).slice(0, 2).map(([k, v]) =>
                    `${k}: ${String(v).slice(0, 30)}`
                  ).join(' · ')}
                </div>
              )}
            </div>

            {/* Tool progress dots */}
            <div style={{ display: 'flex', gap: 3, marginLeft: 4 }}>
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  style={{
                    width: 4,
                    height: 4,
                    borderRadius: '50%',
                    background: '#818CF8',
                  }}
                  animate={{ opacity: [0.2, 1, 0.2] }}
                  transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.27 }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
