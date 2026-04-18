import { useEffect, useRef } from "react";

type Props = {
  stream: MediaStream | null;
  className?: string;
};

export default function Waveform({ stream, className }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!stream) return;
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const ac = new AudioContext();
    const src = ac.createMediaStreamSource(stream);
    const analyser = ac.createAnalyser();
    analyser.fftSize = 1024;
    src.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    let raf = 0;

    const draw = () => {
      raf = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(data);
      const { width: W, height: H } = canvas;
      ctx.clearRect(0, 0, W, H);
      const g = ctx.createLinearGradient(0, 0, W, 0);
      g.addColorStop(0, "rgba(124,92,255,0.9)");
      g.addColorStop(0.5, "rgba(255,122,198,0.9)");
      g.addColorStop(1, "rgba(56,189,248,0.9)");
      ctx.strokeStyle = g;
      ctx.lineWidth = 2;
      ctx.beginPath();
      const step = W / data.length;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        const y = H / 2 + v * H * 0.45;
        if (i === 0) ctx.moveTo(0, y);
        else ctx.lineTo(i * step, y);
      }
      ctx.stroke();
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      ac.close();
    };
  }, [stream]);

  return (
    <canvas
      ref={ref}
      width={1200}
      height={80}
      className={className}
    />
  );
}
