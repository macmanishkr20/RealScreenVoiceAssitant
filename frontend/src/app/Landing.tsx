import { motion } from "framer-motion";
import Orb from "../ui/Orb";
import MagneticCTA from "../ui/MagneticCTA";

const HEADLINE = "See what you see.";
const SUB = "Hear what you ask.";

const wordVariants = {
  hidden: { opacity: 0, y: 28, filter: "blur(8px)" },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { delay: 0.15 + i * 0.07, duration: 0.9, ease: [0.22, 1, 0.36, 1] },
  }),
};

function Headline({ text, className }: { text: string; className?: string }) {
  const words = text.split(" ");
  return (
    <h1 className={className}>
      {words.map((w, i) => (
        <motion.span
          key={`${w}-${i}`}
          custom={i}
          variants={wordVariants}
          initial="hidden"
          animate="show"
          className="inline-block pr-3"
        >
          {w}
        </motion.span>
      ))}
    </h1>
  );
}

export default function Landing({ onStart }: { onStart: () => void }) {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6">
      <div className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center">
        <Orb className="h-[55vh] w-[55vh] opacity-70" />
      </div>

      <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-ink/40 via-ink/30 to-ink/85" />

      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="absolute top-8 flex w-full max-w-6xl items-center justify-between px-8 text-sm tracking-tight"
      >
        <span className="font-medium">⌘ realtime</span>
        <nav className="flex items-center gap-8 text-white/70">
          <span className="transition-colors hover:text-white">Overview</span>
          <span className="transition-colors hover:text-white">Agents</span>
          <span className="transition-colors hover:text-white">Docs</span>
        </nav>
      </motion.div>

      <div className="z-10 flex flex-col items-center text-center">
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05, duration: 0.7 }}
          className="mb-6 rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-xs font-medium uppercase tracking-[0.18em] text-white/80 backdrop-blur-md"
        >
          Multimodal · Realtime · On-screen
        </motion.p>

        <Headline
          text={HEADLINE}
          className="text-[clamp(3rem,9vw,7rem)] font-semibold leading-[0.95] tracking-tight text-white"
        />
        <Headline
          text={SUB}
          className="mt-1 text-[clamp(3rem,9vw,7rem)] font-semibold leading-[0.95] tracking-tight shimmer-text animate-shimmer"
        />

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.8 }}
          className="mt-8 max-w-xl text-lg leading-relaxed text-white/70"
        >
          Share your screen, speak naturally, and get answers grounded in exactly
          what you&apos;re looking at — streamed back in your ear in under a second.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.95, duration: 0.8 }}
          className="mt-10 flex items-center gap-4"
        >
          <MagneticCTA onClick={onStart}>Start a session</MagneticCTA>
          <span className="text-sm text-white/50">
            ⌘ Grants screen + mic on click
          </span>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.4, duration: 1.2 }}
        className="absolute bottom-6 flex items-center gap-6 text-xs text-white/40"
      >
        <span>Azure OpenAI GPT-5</span>
        <span>·</span>
        <span>WebRTC · 800 ms p50</span>
        <span>·</span>
        <span>Microsoft Agent Framework</span>
      </motion.div>
    </main>
  );
}
