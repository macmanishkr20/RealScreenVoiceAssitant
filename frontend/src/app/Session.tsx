import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
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
  const { open, transcripts, speaking, speak, clearTranscripts } = useControl();
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteAudioRef = useRef<HTMLAudioElement>(null);
  const transcriptScrollRef = useRef<HTMLDivElement>(null);
  const [speakText, setSpeakText] = useState("");

  useEffect(() => {
    if (localVideoRef.current) localVideoRef.current.srcObject = localStream;
  }, [localStream]);

  useEffect(() => {
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = remoteStream;
  }, [remoteStream]);

  useEffect(() => {
    transcriptScrollRef.current?.scrollTo({
      top: transcriptScrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [transcripts.length]);

  const notStarted = status === "idle" || status === "error";
  const finalText = useMemo(
    () => transcripts.filter((t) => t.final).map((t) => t.text).join(" "),
    [transcripts],
  );

  return (
    <main className="relative min-h-screen px-6 py-8">
      <audio ref={remoteAudioRef} autoPlay playsInline className="hidden" />

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
            <StatusPill label={speaking ? "TTS speaking" : "TTS idle"} ok={speaking} />
          </div>
        </header>

        {error && (
          <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        {notStarted && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center gap-4 rounded-3xl border border-white/10 bg-white/5 px-6 py-10 text-center backdrop-blur-md"
          >
            <p className="text-sm text-white/70">
              Click below to grant screen-share and microphone access.
              <br />
              <span className="text-xs text-white/40">
                macOS: if no window picker appears, enable Chrome in{" "}
                <em>System Settings → Privacy &amp; Security → Screen Recording</em>, then reload.
              </span>
            </p>
            <button
              onClick={() => start()}
              className="rounded-full bg-fog px-8 py-3 text-sm font-medium text-ink transition-transform hover:scale-[1.02]"
            >
              Grant screen + mic
            </button>
          </motion.div>
        )}

        <div className="grid gap-6 md:grid-cols-[3fr_2fr]">
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
            <div className="border-t border-white/5 bg-black/30 px-4 py-3">
              <Waveform stream={localStream} className="h-16 w-full" />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="flex flex-col overflow-hidden rounded-3xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-md"
          >
            <div className="flex items-center justify-between px-5 py-3 text-xs uppercase tracking-[0.18em] text-white/50">
              <span>Live transcript</span>
              <button
                onClick={clearTranscripts}
                className="text-white/50 transition-colors hover:text-white"
              >
                clear
              </button>
            </div>
            <div
              ref={transcriptScrollRef}
              className="h-64 overflow-y-auto px-5 py-4 text-sm leading-relaxed text-white/90"
            >
              {transcripts.length === 0 && (
                <div className="text-white/40">
                  {status === "connected"
                    ? "Start talking — your voice will transcribe here."
                    : "Waiting for connection…"}
                </div>
              )}
              <AnimatePresence initial={false}>
                {transcripts.map((t) => (
                  <motion.div
                    key={t.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: t.final ? 1 : 0.6, y: 0 }}
                    transition={{ duration: 0.25 }}
                    className={`mb-1 ${t.final ? "text-white" : "text-white/60 italic"}`}
                  >
                    {t.text}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur-md">
          <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-[0.18em] text-white/50">
            <span>Speak (server TTS → your ear)</span>
            {finalText && (
              <span className="normal-case tracking-normal text-white/40">
                last heard: "{finalText.slice(-60)}"
              </span>
            )}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const t = speakText.trim();
              if (!t) return;
              speak(t);
              setSpeakText("");
            }}
            className="flex gap-2"
          >
            <input
              value={speakText}
              onChange={(e) => setSpeakText(e.target.value)}
              placeholder='Type something to hear it back, e.g. "Hello from GPT"'
              className="flex-1 rounded-full border border-white/15 bg-black/40 px-5 py-3 text-sm text-white placeholder:text-white/40 focus:border-white/40 focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-full bg-fog px-5 py-3 text-sm font-medium text-ink transition-transform hover:scale-[1.02]"
            >
              Speak
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
