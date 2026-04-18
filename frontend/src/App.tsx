import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Landing from "./app/Landing";
import Session from "./app/Session";

export default function App() {
  const [route, setRoute] = useState<"landing" | "session">("landing");

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) * 100;
      const y = (e.clientY / window.innerHeight) * 100;
      document.documentElement.style.setProperty("--cursor-x", `${x}%`);
      document.documentElement.style.setProperty("--cursor-y", `${y}%`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div className="gradient-mesh min-h-screen">
      <AnimatePresence mode="wait">
        {route === "landing" ? (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            <Landing onStart={() => setRoute("session")} />
          </motion.div>
        ) : (
          <motion.div
            key="session"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            <Session onExit={() => setRoute("landing")} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
