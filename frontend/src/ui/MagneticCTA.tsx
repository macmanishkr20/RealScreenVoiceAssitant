import { motion, useMotionValue, useSpring } from "framer-motion";
import { useRef, type ReactNode } from "react";

type Props = {
  onClick?: () => void;
  children: ReactNode;
};

export default function MagneticCTA({ onClick, children }: Props) {
  const ref = useRef<HTMLButtonElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 250, damping: 18, mass: 0.6 });
  const sy = useSpring(y, { stiffness: 250, damping: 18, mass: 0.6 });

  return (
    <motion.button
      ref={ref}
      onClick={onClick}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        x.set((e.clientX - cx) * 0.35);
        y.set((e.clientY - cy) * 0.35);
      }}
      onMouseLeave={() => {
        x.set(0);
        y.set(0);
      }}
      style={{ x: sx, y: sy }}
      whileTap={{ scale: 0.96 }}
      className="relative inline-flex h-14 items-center justify-center rounded-full bg-fog px-9 text-base font-medium text-ink shadow-[0_10px_40px_-10px_rgba(255,255,255,0.5)] transition-shadow hover:shadow-[0_20px_60px_-10px_rgba(124,92,255,0.6)]"
    >
      {children}
      <span className="ml-2 text-xl leading-none">→</span>
    </motion.button>
  );
}
