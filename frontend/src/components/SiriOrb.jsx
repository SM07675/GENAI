import React, { useRef, useMemo, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { Environment, MeshTransmissionMaterial, Sparkles } from "@react-three/drei";
import * as THREE from "three";
import { useAppStore, ORB_STATES } from "../store/appStore";

// ==========================================
// 🎵 1. AUDIO FREQUENCY ANALYZER
// ==========================================
function useAudioFrequencies(audioElement, state) {
  const audioData = useRef({ low: 0, mid: 0, high: 0, raw: 0 });
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceRef = useRef(null);

  useEffect(() => {
    if (!audioElement) return;
    const initAudio = () => {
      if (!audioCtxRef.current) {
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          analyser.smoothingTimeConstant = 0.8; // Very smooth for fluid look
          const source = ctx.createMediaElementSource(audioElement);
          source.connect(analyser);
          analyser.connect(ctx.destination);
          audioCtxRef.current = ctx;
          analyserRef.current = analyser;
          sourceRef.current = source;
        } catch (e) {
          console.warn("AudioContext init failed:", e);
        }
      }
    };
    audioElement.addEventListener('play', initAudio);
    return () => audioElement.removeEventListener('play', initAudio);
  }, [audioElement]);

  useEffect(() => {
    let animationId;
    const dataArray = new Uint8Array(128);

    const loop = () => {
      if (analyserRef.current && state === ORB_STATES.SPEAKING) {
        analyserRef.current.getByteFrequencyData(dataArray);
        let low = 0, mid = 0, high = 0;
        for (let i = 0; i < 5; i++) low += dataArray[i];
        for (let i = 5; i < 25; i++) mid += dataArray[i];
        for (let i = 25; i < 100; i++) high += dataArray[i];

        low = (low / 5) / 255;
        mid = (mid / 20) / 255;
        high = (high / 75) / 255;

        audioData.current.low += (low - audioData.current.low) * 0.15;
        audioData.current.mid += (mid - audioData.current.mid) * 0.15;
        audioData.current.high += (high - audioData.current.high) * 0.15;
        audioData.current.raw = Math.max(low, mid, high);
      } else {
        audioData.current.low *= 0.95;
        audioData.current.mid *= 0.95;
        audioData.current.high *= 0.95;
        audioData.current.raw *= 0.95;
      }
      animationId = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(animationId);
  }, [state]);

  return audioData;
}

// ==========================================
// 🌌 2. GLSL SIMPLEX NOISE LIBRARY
// ==========================================
const snoiseGLSL = `
vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
float snoise(vec3 v){ 
  const vec2  C = vec2(1.0/6.0, 1.0/3.0) ;
  const vec4  D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy) );
  vec3 x0 =   v - i + dot(i, C.xxx) ;
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min( g.xyz, l.zxy );
  vec3 i2 = max( g.xyz, l.zxy );
  vec3 x1 = x0 - i1 + 1.0 * C.xxx;
  vec3 x2 = x0 - i2 + 2.0 * C.xxx;
  vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;
  i = mod(i, 289.0 ); 
  vec4 p = permute( permute( permute( 
             i.z + vec4(0.0, i1.z, i2.z, 1.0 ))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0 )) 
           + i.x + vec4(0.0, i1.x, i2.x, 1.0 ));
  float n_ = 1.0/7.0; 
  vec3  ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z *ns.z);  
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_ );    
  vec4 x = x_ *ns.x + ns.yyyy;
  vec4 y = y_ *ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4( x.xy, y.xy );
  vec4 b1 = vec4( x.zw, y.zw );
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ;
  vec3 p0 = vec3(a0.xy,h.x);
  vec3 p1 = vec3(a0.zw,h.y);
  vec3 p2 = vec3(a1.xy,h.z);
  vec3 p3 = vec3(a1.zw,h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) );
}
`;

// ==========================================
// 💎 3. PREMIUM LIQUID-ENERGY ORB
// ==========================================
function LiquidEnergyOrb({ state, amplitude, audioData }) {
  const liquidRef = useRef();
  const nucleusRef = useRef();
  const particlesRef = useRef();
  const glassRef = useRef();
  const currentGesture = useAppStore((s) => s.currentGesture);

  const geometry = useMemo(() => new THREE.IcosahedronGeometry(1.5, 64), []);
  const liquidGeometry = useMemo(() => new THREE.IcosahedronGeometry(1.4, 64), []);
  const nucleusGeometry = useMemo(() => new THREE.IcosahedronGeometry(0.3, 32), []);

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uAudioLow: { value: 0 },
    uAudioMid: { value: 0 },
    uAudioHigh: { value: 0 },
    uState: { value: 0 },
    uColorBase: { value: new THREE.Color("#06b6d4") },
    uColorAccent: { value: new THREE.Color("#818cf8") },
  }), []);

  // Volumetric Plasma Shader
  const liquidMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms,
      vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec3 vViewPosition;
        void main() {
          vUv = uv;
          vNormal = normalize(normalMatrix * normal);
          vPosition = position;
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          vViewPosition = -mvPosition.xyz;
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        ${snoiseGLSL}
        uniform float uTime;
        uniform vec3 uColorBase;
        uniform vec3 uColorAccent;
        uniform float uAudioLow;
        uniform float uState;
        
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec3 vViewPosition;

        void main() {
          vec3 normal = normalize(vNormal);
          vec3 viewDir = normalize(vViewPosition);
          
          float fresnel = dot(viewDir, normal);
          fresnel = clamp(fresnel, 0.0, 1.0);
          float edgeFade = pow(fresnel, 1.5);

          float time = uTime * 0.15;
          
          float noise = snoise(vPosition * 1.2 + vec3(time, time * 0.5, -time));
          
          float audioTime = uTime * (0.2 + uAudioLow * 0.5);
          noise += snoise(vPosition * 2.5 - vec3(0.0, audioTime, audioTime * 0.5)) * (0.3 + uAudioLow * 0.5);

          float colorMix = smoothstep(-0.4, 0.6, noise);
          vec3 plasmaColor = mix(uColorBase, uColorAccent, colorMix);

          float alpha = smoothstep(-0.3, 0.5, noise) * 0.8;
          
          alpha *= edgeFade;

          if (uState == 3.0) {
             float ripple = snoise(vPosition * 5.0 + uTime * 2.0);
             plasmaColor += vec3(ripple * 0.1);
          }

          gl_FragColor = vec4(plasmaColor, alpha);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide
    });
  }, [uniforms]);

  // Nucleus Material
  const nucleusMaterial = useMemo(() => new THREE.MeshBasicMaterial({ 
    color: new THREE.Color("#ffffff"), 
    transparent: true,
    opacity: 0.9 
  }), []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const u = uniforms;
    u.uTime.value = t;
    
    let rawAmp = (state === ORB_STATES.SPEAKING && audioData.current.raw === 0) ? amplitude : 0;
    
    u.uAudioLow.value = audioData.current.low + rawAmp;
    u.uAudioMid.value = audioData.current.mid + rawAmp;
    u.uAudioHigh.value = audioData.current.high + rawAmp;

    if (liquidRef.current) {
        liquidRef.current.rotation.y = t * 0.05;
        liquidRef.current.rotation.z = t * 0.02;
    }

    if (particlesRef.current) {
        particlesRef.current.rotation.y = t * 0.02;
        particlesRef.current.rotation.y += (u.uAudioHigh.value * 0.05);
    }
    
    if (nucleusRef.current) {
        let scale = 1.0 + Math.sin(t * 1.5) * 0.05;
        scale += u.uAudioMid.value * 0.8;
        nucleusRef.current.scale.set(scale, scale, scale);
        
        nucleusMaterial.color.lerpColors(
            new THREE.Color("#ffffff"), 
            new THREE.Color("#06b6d4"), 
            u.uAudioMid.value
        );
    }

    // Color States — now gesture-aware during SPEAKING
    let targetBase = new THREE.Color("#06b6d4");   // Electric Cyan
    let targetAccent = new THREE.Color("#818cf8"); // Indigo
    let stateNum = 0;

    if (state === ORB_STATES.SPEAKING) {
        // Use delivery cue gesture color if available
        if (currentGesture && currentGesture.color) {
            targetBase = new THREE.Color(currentGesture.color);
            // Complementary accent: use a lighter/shifted version
            targetAccent = new THREE.Color(currentGesture.color).offsetHSL(0.15, 0, 0.1);
        } else {
            targetBase = new THREE.Color("#d946ef");   // Magenta
            targetAccent = new THREE.Color("#06b6d4"); // Cyan
        }
        stateNum = 2;
    } else if (state === ORB_STATES.THINKING) {
        targetBase = new THREE.Color("#6366f1");   // Deep Indigo
        targetAccent = new THREE.Color("#ec4899"); // Soft Pink
        stateNum = 3;
    } else if (state === ORB_STATES.LISTENING) {
        targetBase = new THREE.Color("#a855f7");   // Purple
        targetAccent = new THREE.Color("#0ea5e9"); // Ice Blue
        stateNum = 1;
    }

    u.uColorBase.value.lerp(targetBase, 0.05);
    u.uColorAccent.value.lerp(targetAccent, 0.05);
    u.uState.value = stateNum;
  });

  return (
    <group>
      {/* 1. The Energy Nucleus (Brain) */}
      <mesh ref={nucleusRef} geometry={nucleusGeometry} material={nucleusMaterial} />

      {/* 2. The Liquid Plasma Core */}
      <mesh ref={liquidRef} geometry={liquidGeometry} material={liquidMaterial} />

      {/* 3. The Stable Glass Shell */}
      <mesh ref={glassRef} geometry={geometry}>
        <MeshTransmissionMaterial 
          backside
          backsideThickness={1.0}
          thickness={1.5}
          chromaticAberration={0.03}
          anisotropicBlur={0.1}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
          roughness={0.05}
          ior={1.5}
          color="#a5f3fc" // Ice blue glass tint
          transparent
          opacity={0.8}
        />
      </mesh>

      {/* 4. Magnetic Orbiting Particles */}
      <group ref={particlesRef}>
        <Sparkles 
          count={100} 
          scale={5} 
          size={2} 
          speed={0.2} 
          opacity={0.5} 
          color="#06b6d4" 
        />
      </group>
    </group>
  );
}

// ==========================================
// 🚀 4. MAIN COMPONENT (THREE.JS CANVAS)
// ==========================================
export default function SiriOrb({ state = ORB_STATES.IDLE, amplitude = 0 }) {
  const assistantAudioElement = useAppStore((s) => s.assistantAudioElement);
  const audioData = useAudioFrequencies(assistantAudioElement, state);

  return (
    <div className="relative flex items-center justify-center w-full h-[320px] select-none overflow-hidden">
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }}>
        
        {/* Environment Map for Glass Reflections */}
        <Environment preset="city" />
        
        <LiquidEnergyOrb state={state} amplitude={amplitude} audioData={audioData} />
        
        {/* Cinematic Post-Processing Glow (Subtle) */}
        <EffectComposer disableNormalPass>
          <Bloom 
            luminanceThreshold={0.6} 
            luminanceSmoothing={0.9} 
            intensity={0.8} 
            radius={0.7}
            mipmapBlur
          />
        </EffectComposer>
        
      </Canvas>
    </div>
  );
}
