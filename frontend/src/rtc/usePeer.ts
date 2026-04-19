import { useCallback, useEffect, useRef, useState } from "react";
import { getSessionId } from "../session";

const BACKEND_WS =
  (import.meta.env.VITE_BACKEND_WS as string | undefined) ?? "ws://127.0.0.1:8000";
const TOKEN = (import.meta.env.VITE_SESSION_TOKEN as string | undefined) ?? "local-dev-token";

type Status = "idle" | "requesting" | "connecting" | "connected" | "error";

const log = (...args: unknown[]) => console.log("[rtc]", ...args);

export function usePeer() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stop = useCallback(() => {
    log("stop");
    pcRef.current?.close();
    pcRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setLocalStream(null);
    setRemoteStream(null);
    setStatus("idle");
  }, []);

  const start = useCallback(async () => {
    try {
      setError(null);
      setStatus("requesting");

      log("getDisplayMedia");
      const display = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 15, max: 30 } },
        audio: false,
      });
      log("getUserMedia(audio)");
      const mic = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });

      const combined = new MediaStream([
        ...display.getVideoTracks(),
        ...mic.getAudioTracks(),
      ]);
      streamRef.current = combined;
      setLocalStream(combined);
      log("local tracks", combined.getTracks().map((t) => `${t.kind}:${t.label}`));

      setStatus("connecting");
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      pcRef.current = pc;

      const remote = new MediaStream();
      pc.ontrack = (e) => {
        log("ontrack", e.track.kind);
        remote.addTrack(e.track);
        setRemoteStream(new MediaStream(remote.getTracks()));
      };
      pc.onconnectionstatechange = () => {
        log("pc.connectionState", pc.connectionState);
        if (pc.connectionState === "connected") setStatus("connected");
        if (pc.connectionState === "failed") {
          setStatus("error");
          setError("peer connection failed");
        }
      };
      pc.oniceconnectionstatechange = () => log("pc.iceState", pc.iceConnectionState);

      for (const track of combined.getTracks()) pc.addTrack(track, combined);

      const sid = getSessionId();
      const url = `${BACKEND_WS}/ws/signaling?token=${TOKEN}&sessionId=${sid}`;
      log("ws connect", url);
      const ws = new WebSocket(url);
      wsRef.current = ws;
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => {
          log("ws open");
          resolve();
        };
        ws.onerror = () => reject(new Error("signaling socket failed"));
        setTimeout(() => reject(new Error("signaling open timeout")), 5_000);
      });

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      log("sending offer");

      ws.send(
        JSON.stringify({
          type: "offer",
          sdp: pc.localDescription!.sdp,
          sdpType: pc.localDescription!.type,
        }),
      );

      await new Promise<void>((resolve, reject) => {
        ws.onmessage = async (ev) => {
          const msg = JSON.parse(ev.data);
          log("ws recv", msg.type);
          if (msg.type === "answer") {
            await pc.setRemoteDescription({ type: msg.sdpType, sdp: msg.sdp });
            resolve();
          }
        };
        ws.onerror = () => reject(new Error("signaling error"));
        setTimeout(() => reject(new Error("answer timeout")), 10_000);
      });
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      console.error("[rtc] start failed:", m);
      setError(m);
      setStatus("error");
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { status, error, localStream, remoteStream, start, stop };
}
