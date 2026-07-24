import React, { useRef, useState, useEffect } from 'react';
import { motion, useAnimation } from 'framer-motion';

const DRAG_THRESHOLD = 5;

export default function MovableAssistant({ children }) {
  const containerRef = useRef(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const dragStartPos = useRef({ x: 0, y: 0 });
  const initialPos = useRef({ x: 0, y: 0 });
  const hasMoved = useRef(false);
  
  const controls = useAnimation();

  useEffect(() => {
    const saved = localStorage.getItem('genie-face-position');
    const hasMovedBefore = localStorage.getItem('genie-face-moved');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setPosition(parsed);
        controls.set(parsed);
      } catch (e) {}
    }
    if (!hasMovedBefore && !saved) {
      setShowTooltip(true);
    }
  }, [controls]);

  const constrainPosition = (x, y) => {
    if (!containerRef.current) return { x, y };
    const rect = containerRef.current.getBoundingClientRect();
    const padding = 20;
    
    // Bounds relative to the center
    const maxX = (window.innerWidth - rect.width) / 2 - padding;
    const maxY = (window.innerHeight - rect.height) / 2 - padding;
    
    return {
      x: Math.max(-maxX, Math.min(maxX, x)),
      y: Math.max(-maxY, Math.min(maxY, y))
    };
  };

  const handlePointerDown = (e) => {
    // Only primary button
    if (e.button !== 0 && e.type !== 'touchstart') return;
    
    e.target.setPointerCapture(e.pointerId);
    dragStartPos.current = { x: e.clientX, y: e.clientY };
    initialPos.current = { ...position };
    hasMoved.current = false;
  };

  const handlePointerMove = (e) => {
    if (!e.target.hasPointerCapture(e.pointerId)) return;
    
    const dx = e.clientX - dragStartPos.current.x;
    const dy = e.clientY - dragStartPos.current.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    if (!hasMoved.current && dist > DRAG_THRESHOLD) {
      hasMoved.current = true;
      setIsDragging(true);
      setShowTooltip(false);
      localStorage.setItem('genie-face-moved', 'true');
    }
    
    if (hasMoved.current) {
      const newPos = constrainPosition(initialPos.current.x + dx, initialPos.current.y + dy);
      setPosition(newPos);
      controls.set(newPos);
    }
  };

  const handlePointerUp = (e) => {
    if (!e.target.hasPointerCapture(e.pointerId)) return;
    e.target.releasePointerCapture(e.pointerId);
    
    if (hasMoved.current) {
      setIsDragging(false);
      localStorage.setItem('genie-face-position', JSON.stringify(position));
    }
  };

  const handleDoubleClick = () => {
    const center = { x: 0, y: 0 };
    setPosition(center);
    controls.start({
      x: 0, y: 0,
      transition: { type: 'spring', stiffness: 200, damping: 20 }
    });
    localStorage.setItem('genie-face-position', JSON.stringify(center));
  };

  return (
    <motion.div
      ref={containerRef}
      animate={controls}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onDoubleClick={handleDoubleClick}
      className="relative touch-none"
      style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
    >
      {children}
      
      {showTooltip && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute -bottom-10 left-1/2 -translate-x-1/2 whitespace-nowrap bg-white/90 text-slate-700 px-4 py-2 rounded-full text-sm shadow-md pointer-events-none"
        >
          Drag Genie anywhere ✨
        </motion.div>
      )}
    </motion.div>
  );
}
