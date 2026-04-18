import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { usePeer } from "../rtc/usePeer";
import { useControl } from "../ws/useControl";
import Waveform from "../ui/Waveform";

function StatusPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/80 backdrop-blur-md">
      <span
        className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-white/30"}`}
      />
      {label}
    </div>
  );
}

export default function Session({ onExit }: { onExit: () => void }) {
  const { status, error, localStream, remoteStream, start, stop } = usePeer();
  const { open, messages, send } = useControl();
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const [text, setText] = useState("");

  useEffect(() => {
    if (localVideoRef.current) localVideoRef.current.srcObject = localStream;
  }, [localStream]);
  useEffect(() => {
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = remoteStream;
  }, [remoteStream]);

  useEffect(() => {
    start();
  }, [start]);

  return (
    <main className="relative min-h-screen px-6 py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex items-center justify-between">
          <motion.button
            onClick={() => {
              stop();
              onExit();
            }}
            whileHover={{ x: -2 }}
            className="text-sm text-white/70 transition-colors hover:text-white"
          >
            ← Back
          </motion.button>
          <div className="flex gap-2">
            <StatusPill label={`RTC: ${status}`} ok={status === "connected"} />
            <StatusPill label={`Control: ${open ? "open" : "closed"}`} ok={open} />
          </div>
        </header>

        {error && (
          <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl backdrop-blur-md"
          >
            <div className="flex items-center justify-between px-5 py-3 text-xs uppercase tracking-[0.18em] text-white/50">
              <span>Your screen</span>
              <span>local</span>
            </div>
            <video
              ref={localVideoRef}
              autoPlay
              muted
              playsInline
              className="aspect-video w-full bg-black object-contain"
            />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl backdrop-blur-md"
          >
            <div className="flex items-center justify-between px-5 py-3 text-xs uppercase tracking-[0.18em] text-white/50">
              <span>Echo from server</span>
              <span>remote</span>
            </div>
            <video
              ref={remoteVideoRef}
              autoPlay
              playsInline
              className="aspect-video w-full bg-black object-contain"
            />
          </motion.div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
          <Waveform stream={localStream} className="h-20 w-full" />
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-md">
          <div className="mb-3 text-xs uppercase tracking-[0.18em] text-white/50">
            Control channel
          </div>
          <div className="mb-4 h-40 overflow-y-auto rounded-xl bg-black/30 p-3 text-sm text-white/80">
            {messages.length === 0 && (
              <div className="text-white/40">no messages yet</div>
            )}
            {messages.map((m, i) => (
              <div key={i} className="py-0.5 font-mono text-xs">
                {JSON.stringify(m)}
              </div>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!text.trim()) return;
              send(text);
              setText("");
            }}
            className="flex gap-2"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type a test message…"
              className="flex-1 rounded-full border border-white/15 bg-black/40 px-5 py-3 text-sm text-white placeholder:text-white/40 focus:border-white/40 focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-full bg-fog px-5 py-3 text-sm font-medium text-ink transition-transform hover:scale-[1.02]"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
