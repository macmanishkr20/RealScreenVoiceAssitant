import { useCallback, useEffect, useRef, useState } from "react";

const BACKEND_WS =
  (import.meta.env.VITE_BACKEND_WS as string | undefined) ?? "ws://127.0.0.1:8000";
const TOKEN = (import.meta.env.VITE_SESSION_TOKEN as string | undefined) ?? "local-dev-token";

export type ControlMsg =
  | { type: "hello"; milestone: string }
  | { type: "pong" }
  | { type: "echo"; text: string };

export function useControl() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ControlMsg[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${BACKEND_WS}/ws/control?token=${TOKEN}`);
    wsRef.current = ws;
    ws.onopen = () => setOpen(true);
    ws.onclose = () => setOpen(false);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as ControlMsg;
        setMessages((m) => [...m, msg]);
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, []);

  const send = useCallback((text: string) => {
    wsRef.current?.send(JSON.stringify({ type: "text", text }));
  }, []);

  return { open, messages, send };
}
