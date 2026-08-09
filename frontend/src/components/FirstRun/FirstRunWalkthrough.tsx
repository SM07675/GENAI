import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const STORAGE_KEY = 'genie_first_run_completed';

interface FirstRunWalkthroughProps {
  onComplete?: () => void;
}

export function FirstRunWalkthrough({ onComplete }: FirstRunWalkthroughProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    try {
      const completed = localStorage.getItem(STORAGE_KEY);
      if (!completed) {
        setIsOpen(true);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const handleFinish = () => {
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      /* ignore */
    }
    setIsOpen(false);
    if (onComplete) onComplete();
  };

  const steps = [
    {
      title: "Welcome to Genie AI OS",
      subtitle: "Your Voice-First AI Personal Assistant & Desktop Companion",
      description:
        "Genie is designed to talk, listen, code, execute actions, and sit beside you on Windows 11. Say 'Hey Genie' or press the mic button anytime.",
      icon: "✨",
    },
    {
      title: "Meet Companion Mode & Quick Look",
      subtitle: "Screen Awareness That Stays Quiet Until Needed",
      description:
        "Companion Mode watches your active screen surface to help with errors, gaming, or writing. Press Ctrl+Shift+G or click the floating orb for an instant Quick Look.",
      note: "Companion Mode is OFF by default. Your raw screen captures are never saved or stored.",
      icon: "👁",
    },
    {
      title: "Microphone & Privacy Controls",
      subtitle: "Complete Control Over Voice & Vision",
      description:
        "Genie uses your microphone only when active. You can toggle voice listening, screen awareness, or inspect live diagnostics at any time in Settings.",
      icon: "🎙",
    },
  ];

  if (!isOpen) return null;

  const current = steps[step];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-slate-950/80 backdrop-blur-xl">
        <motion.div
          key={step}
          initial={{ opacity: 0, scale: 0.92, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -10 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="w-full max-w-md p-8 rounded-3xl bg-slate-900/90 border border-cyan-500/30 text-slate-100 shadow-2xl shadow-cyan-500/10 flex flex-col justify-between min-h-[380px]"
        >
          {/* Header & Step Indicator */}
          <div>
            <div className="flex items-center justify-between mb-6">
              <div className="flex gap-1.5">
                {steps.map((_, idx) => (
                  <div
                    key={idx}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      idx === step ? 'w-8 bg-cyan-400' : 'w-2 bg-slate-800'
                    }`}
                  />
                ))}
              </div>
              <button
                onClick={handleFinish}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                Skip
              </button>
            </div>

            {/* Content */}
            <div className="text-center space-y-3">
              <div className="text-4xl mb-2">{current.icon}</div>
              <h2 className="text-xl font-bold tracking-tight text-slate-100">{current.title}</h2>
              <p className="text-xs font-semibold text-cyan-300 uppercase tracking-wider">{current.subtitle}</p>
              <p className="text-sm text-slate-300 leading-relaxed pt-2">{current.description}</p>

              {current.note && (
                <div className="mt-4 p-3 rounded-xl bg-cyan-950/40 border border-cyan-500/20 text-xs text-cyan-200">
                  {current.note}
                </div>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-6 border-t border-slate-800 mt-6">
            {step > 0 ? (
              <button
                onClick={() => setStep(step - 1)}
                className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
              >
                Back
              </button>
            ) : <div />}

            <button
              onClick={() => {
                if (step < steps.length - 1) {
                  setStep(step + 1);
                } else {
                  handleFinish();
                }
              }}
              className="px-6 py-2.5 rounded-xl bg-cyan-500/20 border border-cyan-400 text-cyan-200 font-medium text-xs hover:bg-cyan-500/30 transition-all shadow-lg shadow-cyan-500/10"
            >
              {step < steps.length - 1 ? 'Next' : 'Get Started'}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
