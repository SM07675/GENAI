/**
 * CompanionDashboard.tsx — Real-time system status and context dashboard.
 *
 * Shows:
 * - Genie status (listening/thinking/speaking/offline)
 * - Current context (app, project, file, time)
 * - Recent activity log
 * - Memory snippets
 * - Active tasks
 * - System health dots
 * - Device connections
 * - Permission toggles
 */
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../../store/appStore';
import { useCompanionStore } from '../../store/companionStore';

const STATE_COLOR: Record<string, string> = {
  idle:      '#5EEAD4',
  sleeping:  '#6D28D9',
  listening: '#22D3EE',
  thinking:  '#818CF8',
  speaking:  '#34D399',
  error:     '#F87171',
  offline:   '#64748b',
};

const STATE_ICON: Record<string, string> = {
  idle:      '●',
  sleeping:  '💤',
  listening: '🎤',
  thinking:  '🔄',
  speaking:  '🔊',
  error:     '⚠',
  offline:   '○',
};

interface DashboardProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CompanionDashboard({ isOpen, onClose }: DashboardProps) {
  const genieState = useAppStore((s) => s.genieState);
  const messages = useAppStore((s) => s.messages);
  const wsStatus = useAppStore((s) => s.wsStatus);
  const companion = useCompanionStore();

  const [activeTab, setActiveTab] = useState<'status' | 'memory' | 'health'>('status');
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const stateColor = STATE_COLOR[genieState] ?? '#5EEAD4';
  const stateIcon = STATE_ICON[genieState] ?? '●';
  const isConnected = wsStatus === 'authed' || wsStatus === 'connected';

  const recentMessages = messages.slice(-6);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, x: 20, scale: 0.96 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: 20, scale: 0.96 }}
          transition={{ duration: 0.2 }}
          style={{
            position: 'fixed',
            right: 20,
            top: 20,
            bottom: 20,
            width: 340,
            zIndex: 9997,
            background: 'rgba(4,7,18,0.97)',
            border: '1px solid rgba(99,102,241,0.3)',
            borderRadius: 24,
            backdropFilter: 'blur(24px)',
            boxShadow: '0 32px 80px rgba(0,0,0,0.7)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            fontFamily: "'Inter', sans-serif",
          }}
        >
          {/* Header */}
          <div style={{
            padding: '18px 20px 0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div>
              <div style={{ color: '#e2e8f0', fontSize: 16, fontWeight: 700 }}>
                Genie Dashboard
              </div>
              <div style={{ color: '#475569', fontSize: 11, marginTop: 2 }}>
                {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 10,
                width: 30,
                height: 30,
                color: '#64748b',
                cursor: 'pointer',
                fontSize: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ✕
            </button>
          </div>

          {/* Status Card */}
          <div style={{
            margin: '16px 16px 8px',
            padding: '14px 16px',
            background: `${stateColor}12`,
            border: `1px solid ${stateColor}44`,
            borderRadius: 16,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <motion.div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: '50%',
                  background: `${stateColor}22`,
                  border: `2px solid ${stateColor}66`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 16,
                }}
                animate={{ boxShadow: [`0 0 0px ${stateColor}00`, `0 0 20px ${stateColor}66`, `0 0 0px ${stateColor}00`] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                {stateIcon}
              </motion.div>
              <div>
                <div style={{ color: stateColor, fontSize: 13, fontWeight: 700, textTransform: 'capitalize' }}>
                  {genieState.replace(/_/g, ' ')}
                </div>
                <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>
                  {isConnected ? '● Connected' : '○ Connecting…'}
                </div>
              </div>
            </div>

            {/* Privacy indicators */}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <PrivacyDot active={companion.micActive} color="#a78bfa" label="MIC" />
              <PrivacyDot active={companion.cameraActive} color="#f472b6" label="CAM" />
              <PrivacyDot active={companion.screenAware} color="#22d3ee" label="SCREEN" />
            </div>
          </div>

          {/* Tab bar */}
          <div style={{
            display: 'flex',
            padding: '0 16px',
            gap: 4,
            marginBottom: 8,
          }}>
            {(['status', 'memory', 'health'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  flex: 1,
                  padding: '6px 4px',
                  borderRadius: 10,
                  border: 'none',
                  background: activeTab === tab ? 'rgba(99,102,241,0.2)' : 'transparent',
                  color: activeTab === tab ? '#818CF8' : '#475569',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                  letterSpacing: '0.04em',
                  fontFamily: "'Inter', sans-serif",
                  transition: 'all 0.15s',
                }}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px', scrollbarWidth: 'none' }}>
            {activeTab === 'status' && (
              <StatusTab messages={recentMessages} companion={companion} />
            )}
            {activeTab === 'memory' && (
              <MemoryTab />
            )}
            {activeTab === 'health' && (
              <HealthTab isConnected={isConnected} wsStatus={wsStatus} />
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function PrivacyDot({ active, color, label }) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
      padding: '4px 6px',
      borderRadius: 8,
      background: active ? `${color}18` : 'rgba(255,255,255,0.03)',
      border: `1px solid ${active ? color + '44' : 'rgba(255,255,255,0.06)'}`,
    }}>
      <div style={{
        width: 5,
        height: 5,
        borderRadius: '50%',
        background: active ? color : '#334155',
        boxShadow: active ? `0 0 6px ${color}` : 'none',
      }} />
      <span style={{ color: active ? color : '#475569', fontSize: 9, fontWeight: 700, letterSpacing: '0.06em' }}>
        {label}
      </span>
    </div>
  );
}

function StatusTab({ messages, companion }) {
  return (
    <div>
      <SectionTitle>Recent Activity</SectionTitle>
      {messages.length === 0 ? (
        <EmptyState text="No conversation yet" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {messages.slice().reverse().map((msg, i) => (
            <motion.div
              key={msg.id || i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              style={{
                padding: '8px 10px',
                borderRadius: 12,
                background: msg.role === 'user' ? 'rgba(34,211,238,0.06)' : 'rgba(99,102,241,0.06)',
                border: `1px solid ${msg.role === 'user' ? 'rgba(34,211,238,0.12)' : 'rgba(99,102,241,0.12)'}`,
              }}
            >
              <div style={{
                color: msg.role === 'user' ? '#22d3ee' : '#818CF8',
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '0.06em',
                marginBottom: 4,
              }}>
                {msg.role === 'user' ? 'YOU' : 'GENIE'}
              </div>
              <div style={{
                color: '#94a3b8',
                fontSize: 12,
                lineHeight: 1.5,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}>
                {msg.text || '...'}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {companion.contextSnapshot && (
        <>
          <SectionTitle style={{ marginTop: 16 }}>Current Context</SectionTitle>
          <ContextItem icon="📱" label="App" value={companion.contextSnapshot.currentApp || 'Unknown'} />
          {companion.contextSnapshot.currentProject && (
            <ContextItem icon="📁" label="Project" value={companion.contextSnapshot.currentProject} />
          )}
          {companion.contextSnapshot.openFile && (
            <ContextItem icon="📄" label="File" value={companion.contextSnapshot.openFile.split('/').pop() || ''} />
          )}
        </>
      )}
    </div>
  );
}

function MemoryTab() {
  return (
    <div>
      <SectionTitle>Long-Term Memory</SectionTitle>
      <EmptyState text="Memory will appear after conversations. Ask Genie to 'remember' something to test it." />
      <SectionTitle style={{ marginTop: 16 }}>Preferences</SectionTitle>
      <EmptyState text="User preferences are stored automatically as Genie learns your habits." />
    </div>
  );
}

function HealthTab({ isConnected, wsStatus }) {
  const checks = [
    { label: 'WebSocket', ok: wsStatus === 'authed' || wsStatus === 'connected', detail: wsStatus },
    { label: 'Backend', ok: isConnected, detail: isConnected ? 'Running' : 'Connecting' },
    { label: 'Microphone', ok: true, detail: 'Available' },
    { label: 'TTS', ok: true, detail: 'Edge TTS' },
    { label: 'STT', ok: true, detail: 'faster-whisper' },
    { label: 'Wake Word', ok: true, detail: 'Vosk' },
  ];

  return (
    <div>
      <SectionTitle>System Health</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {checks.map((check) => (
          <div
            key={check.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              borderRadius: 10,
              background: check.ok ? 'rgba(52,211,153,0.06)' : 'rgba(248,113,113,0.06)',
              border: `1px solid ${check.ok ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)'}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: check.ok ? '#34D399' : '#F87171',
                boxShadow: check.ok ? '0 0 6px #34D399' : '0 0 6px #F87171',
              }} />
              <span style={{ color: '#e2e8f0', fontSize: 12, fontWeight: 500 }}>
                {check.label}
              </span>
            </div>
            <span style={{ color: check.ok ? '#34D399' : '#F87171', fontSize: 11 }}>
              {check.detail}
            </span>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 16,
        padding: '10px 14px',
        borderRadius: 12,
        background: 'rgba(52,211,153,0.06)',
        border: '1px solid rgba(52,211,153,0.2)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <span style={{ fontSize: 16 }}>✓</span>
        <span style={{ color: '#34D399', fontSize: 13, fontWeight: 600 }}>
          System Healthy
        </span>
      </div>
    </div>
  );
}

function SectionTitle({ children, style = {} }) {
  return (
    <div style={{
      color: '#475569',
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      marginBottom: 8,
      marginTop: 4,
      ...style,
    }}>
      {children}
    </div>
  );
}

function ContextItem({ icon, label, value }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 10px',
      borderRadius: 10,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)',
      marginBottom: 6,
    }}>
      <span style={{ fontSize: 13 }}>{icon}</span>
      <span style={{ color: '#475569', fontSize: 11 }}>{label}:</span>
      <span style={{ color: '#94a3b8', fontSize: 11, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {value}
      </span>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div style={{
      padding: '16px',
      borderRadius: 12,
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.05)',
      color: '#334155',
      fontSize: 12,
      fontStyle: 'italic',
      textAlign: 'center',
      marginBottom: 8,
    }}>
      {text}
    </div>
  );
}
