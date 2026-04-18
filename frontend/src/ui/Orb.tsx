import { Canvas, useFrame } from "@react-three/fiber";
import { MeshDistortMaterial, Float } from "@react-three/drei";
import { useRef } from "react";
import type { Mesh } from "three";

type Props = {
  /** 0..1 amplitude used to pulse the orb (mic RMS in M2+). */
  amplitude?: number;
  className?: string;
};

function OrbMesh({ amplitude = 0 }: { amplitude?: number }) {
  const ref = useRef<Mesh>(null);
  useFrame((_, dt) => {
    if (!ref.current) return;
    ref.current.rotation.y += dt * 0.15;
    ref.current.rotation.x += dt * 0.05;
    const target = 1 + amplitude * 0.18;
    const cur = ref.current.scale.x;
    const next = cur + (target - cur) * 0.1;
    ref.current.scale.setScalar(next);
  });
  return (
    <Float speed={1.2} rotationIntensity={0.4} floatIntensity={0.6}>
      <mesh ref={ref}>
        <icosahedronGeometry args={[1, 48]} />
        <MeshDistortMaterial
          color="#7c5cff"
          emissive="#3a1f8a"
          emissiveIntensity={0.6}
          distort={0.42}
          speed={1.6}
          roughness={0.15}
          metalness={0.4}
        />
      </mesh>
    </Float>
  );
}

export default function Orb({ amplitude, className }: Props) {
  return (
    <div className={className}>
      <Canvas
        camera={{ position: [0, 0, 3.2], fov: 42 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.35} />
        <directionalLight position={[3, 3, 3]} intensity={1.1} />
        <directionalLight position={[-3, -2, 2]} intensity={0.6} color="#ff7ac6" />
        <OrbMesh amplitude={amplitude} />
      </Canvas>
    </div>
  );
}
