import { useCallback, useEffect, useRef, useState } from "react";

const BACKEND_WS =
  (import.meta.env.VITE_BACKEND_WS as string | undefined) ?? "ws://127.0.0.1:8000";
const TOKEN = (import.meta.env.VITE_SESSION_TOKEN as string | undefined) ?? "local-dev-token";

type Status = "idle" | "requesting" | "connecting" | "connected" | "error";

export function usePeer() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const start = useCallback(async () => {
    try {
      setError(null);
      setStatus("requesting");

      const display = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 15, max: 30 } },
        audio: false,
      });
      const mic = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });

      const combined = new MediaStream([
        ...display.getVideoTracks(),
        ...mic.getAudioTracks(),
      ]);
      setLocalStream(combined);

      setStatus("connecting");
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      pcRef.current = pc;

      const remote = new MediaStream();
      setRemoteStream(remote);
      pc.ontrack = (e) => {
        remote.addTrack(e.track);
        setRemoteStream(new MediaStream(remote.getTracks()));
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") setStatus("connected");
        if (pc.connectionState === "failed" || pc.connectionState === "closed") {
          setStatus("error");
          setError(`peer ${pc.connectionState}`);
        }
      };

      for (const track of combined.getTracks()) pc.addTrack(track, combined);

      const ws = new WebSocket(`${BACKEND_WS}/ws/signaling?token=${TOKEN}`);
      wsRef.current = ws;
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("signaling socket failed"));
      });

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

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
      setError(m);
      setStatus("error");
    }
  }, []);

  const stop = useCallback(() => {
    pcRef.current?.close();
    pcRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    localStream?.getTracks().forEach((t) => t.stop());
    setLocalStream(null);
    setRemoteStream(null);
    setStatus("idle");
  }, [localStream]);

  useEffect(() => () => stop(), [stop]);

  return { status, error, localStream, remoteStream, start, stop };
}
