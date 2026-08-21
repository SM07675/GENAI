import React from 'react';
import { motion } from 'framer-motion';

export interface AgentBadgeProps {
  agent: string;
  isActive?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const AGENT_CONFIGS: Record<string, { label: string; color: string; bg: string; border: string; icon: string }> = {
  general: {
    label: 'General Agent',
    color: '#818cf8',
    bg: 'rgba(129, 140, 248, 0.12)',
    border: 'rgba(129, 140, 248, 0.3)',
    icon: '✦',
  },
  research: {
    label: 'Research Agent',
    color: '#38bdf8',
    bg: 'rgba(56, 189, 248, 0.12)',
    border: 'rgba(56, 189, 248, 0.3)',
    icon: '🔍',
  },
  coding: {
    label: 'Coding Agent',
    color: '#34d399',
    bg: 'rgba(52, 211, 153, 0.12)',
    border: 'rgba(52, 211, 153, 0.3)',
    icon: '💻',
  },
  file: {
    label: 'File Agent',
    color: '#fbbf24',
    bg: 'rgba(251, 191, 36, 0.12)',
    border: 'rgba(251, 191, 36, 0.3)',
    icon: '📁',
  },
  system: {
    label: 'System Agent',
    color: '#f87171',
    bg: 'rgba(248, 113, 113, 0.12)',
    border: 'rgba(248, 113, 113, 0.3)',
    icon: '⚙️',
  },
  media: {
    label: 'Media Agent',
    color: '#e879f9',
    bg: 'rgba(232, 121, 249, 0.12)',
    border: 'rgba(232, 121, 249, 0.3)',
    icon: '🎵',
  },
  browser: {
    label: 'Browser Agent',
    color: '#2dd4bf',
    bg: 'rgba(45, 212, 191, 0.12)',
    border: 'rgba(45, 212, 191, 0.3)',
    icon: '🌐',
  },
  data: {
    label: 'Data Agent',
    color: '#a78bfa',
    bg: 'rgba(167, 139, 250, 0.12)',
    border: 'rgba(167, 139, 250, 0.3)',
    icon: '📊',
  },
  document: {
    label: 'Document Agent',
    color: '#fb923c',
    bg: 'rgba(251, 146, 60, 0.12)',
    border: 'rgba(251, 146, 60, 0.3)',
    icon: '📄',
  },
  productivity: {
    label: 'Productivity Agent',
    color: '#4ade80',
    bg: 'rgba(74, 222, 128, 0.12)',
    border: 'rgba(74, 222, 128, 0.3)',
    icon: '✓',
  },
  planner: {
    label: 'Planner',
    color: '#c084fc',
    bg: 'rgba(192, 132, 252, 0.12)',
    border: 'rgba(192, 132, 252, 0.3)',
    icon: '🗺️',
  },
  verifier: {
    label: 'Verifier',
    color: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.12)',
    border: 'rgba(34, 197, 94, 0.3)',
    icon: '🛡️',
  },
};

export const AgentBadge: React.FC<AgentBadgeProps> = ({ agent, isActive = false, size = 'md' }) => {
  const norm = (agent || 'general').toLowerCase();
  const config = AGENT_CONFIGS[norm] || AGENT_CONFIGS.general;

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3.5 py-1.5 gap-2',
  }[size];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`inline-flex items-center rounded-full font-medium transition-all duration-200 border ${sizeClasses}`}
      style={{
        backgroundColor: config.bg,
        borderColor: isActive ? config.color : config.border,
        color: config.color,
        boxShadow: isActive ? `0 0 12px ${config.bg}` : 'none',
      }}
    >
      <span className="text-[1.1em]">{config.icon}</span>
      <span>{config.label}</span>
      {isActive && (
        <span
          className="w-1.5 h-1.5 rounded-full animate-ping ml-0.5"
          style={{ backgroundColor: config.color }}
        />
      )}
    </motion.div>
  );
};
