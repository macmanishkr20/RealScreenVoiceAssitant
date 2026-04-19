import { useCallback, useEffect, useRef, useState } from "react";
import { getSessionId } from "../session";

const BACKEND_WS =
  (import.meta.env.VITE_BACKEND_WS as string | undefined) ?? "ws://127.0.0.1:8000";
const TOKEN = (import.meta.env.VITE_SESSION_TOKEN as string | undefined) ?? "local-dev-token";

export type ControlMsg =
  | { type: "hello"; milestone: string; sessionId: string }
  | { type: "pong" }
  | { type: "echo"; text: string }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "assistant"; text: string; final: boolean }
  | { type: "speaking"; text: string; state: "start" | "end" };

export type Turn = {
  id: number;
  role: "user" | "assistant";
  text: string;
  final: boolean;
};

export function useControl() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [speaking, setSpeaking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const nextIdRef = useRef(0);

  useEffect(() => {
    const sid = getSessionId();
    const ws = new WebSocket(
      `${BACKEND_WS}/ws/control?token=${TOKEN}&sessionId=${sid}`,
    );
    wsRef.current = ws;
    ws.onopen = () => setOpen(true);
    ws.onclose = () => setOpen(false);
    ws.onmessage = (ev) => {
      let msg: ControlMsg;
      try {
        msg = JSON.parse(ev.data) as ControlMsg;
      } catch {
        return;
      }
      if (msg.type === "transcript" || msg.type === "assistant") {
        const role: Turn["role"] = msg.type === "transcript" ? "user" : "assistant";
        setTurns((prev) => {
          // Collapse streaming partials for the same role at the tail.
          const last = prev[prev.length - 1];
          if (last && last.role === role && !last.final) {
            const next = prev.slice(0, -1);
            next.push({ id: last.id, role, text: msg.text, final: msg.final });
            return next;
          }
          return [
            ...prev,
            { id: nextIdRef.current++, role, text: msg.text, final: msg.final },
          ];
        });
      } else if (msg.type === "speaking") {
        setSpeaking(msg.state === "start");
      }
    };
    return () => ws.close();
  }, []);

  const speak = useCallback((text: string) => {
    wsRef.current?.send(JSON.stringify({ type: "speak", text }));
  }, []);

  const clearTurns = useCallback(() => setTurns([]), []);

  return { open, turns, speaking, speak, clearTurns };
}
