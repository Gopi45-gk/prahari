import { motion } from "framer-motion";
import { useEffect, useState } from "react";

// Simplified India outline path (stylized, hand-tuned for command-center aesthetic).
const INDIA_PATH = "M180,40 L210,55 L235,52 L260,70 L285,72 L300,85 L320,90 L340,80 L360,90 L380,110 L390,135 L385,160 L395,185 L380,210 L360,235 L345,265 L335,295 L320,325 L300,350 L280,375 L255,395 L230,410 L210,420 L195,410 L185,395 L175,375 L170,355 L165,330 L158,310 L150,290 L140,275 L130,260 L120,240 L115,220 L120,200 L130,180 L140,160 L150,140 L155,120 L160,100 L165,80 L170,60 Z";

// Stations: { name, x, y, type: hub|major|minor }
const STATIONS = [
  { name: "New Delhi", x: 230, y: 95, type: "hub" },
  { name: "Mumbai", x: 175, y: 240, type: "hub" },
  { name: "Chennai", x: 270, y: 350, type: "hub" },
  { name: "Kolkata", x: 350, y: 175, type: "hub" },
  { name: "Bengaluru", x: 235, y: 335, type: "hub" },
  { name: "Hyderabad", x: 250, y: 280, type: "hub" },
  { name: "Ahmedabad", x: 180, y: 195, type: "major" },
  { name: "Jaipur", x: 210, y: 145, type: "major" },
  { name: "Lucknow", x: 275, y: 130, type: "major" },
  { name: "Patna", x: 320, y: 145, type: "major" },
  { name: "Bhopal", x: 235, y: 200, type: "major" },
  { name: "Nagpur", x: 260, y: 230, type: "major" },
  { name: "Pune", x: 195, y: 260, type: "major" },
  { name: "Kochi", x: 215, y: 380, type: "major" },
  { name: "Vizag", x: 305, y: 270, type: "minor" },
  { name: "Bhubaneswar", x: 325, y: 220, type: "minor" },
  { name: "Indore", x: 215, y: 200, type: "minor" },
  { name: "Surat", x: 178, y: 215, type: "minor" },
  { name: "Coimbatore", x: 240, y: 365, type: "minor" },
  { name: "Guwahati", x: 390, y: 145, type: "minor" },
];

// Track lines connecting hubs.
const TRACKS: Array<[number, number]> = [
  [0,1],[0,2],[0,3],[0,8],[0,7],[0,9],[1,4],[1,5],[1,6],[1,11],[1,12],
  [2,4],[2,5],[2,14],[2,13],[2,18],[3,9],[3,15],[3,19],[4,5],[4,13],
  [5,11],[5,14],[6,10],[7,8],[7,10],[8,10],[10,11],[11,15],[11,14],
];

const RISK_ZONES = [
  { x: 240, y: 200, r: 28, tone: "warning" },
  { x: 175, y: 240, r: 32, tone: "critical" },
  { x: 320, y: 145, r: 22, tone: "warning" },
];

const INCIDENTS = [
  { x: 240, y: 195, label: "KM 142/7" },
  { x: 320, y: 148, label: "Patna Yard" },
];

export function IndiaMap({
  showLayers = { trains: true, signals: true, stations: true, risk: true, incidents: true, weather: false, tracks: true },
  height = 460,
  compact = false,
}: {
  showLayers?: Partial<{ trains: boolean; signals: boolean; stations: boolean; risk: boolean; incidents: boolean; weather: boolean; tracks: boolean }>;
  height?: number;
  compact?: boolean;
}) {
  const L = { trains: true, signals: true, stations: true, risk: true, incidents: true, weather: false, tracks: true, ...showLayers };

  // Generate animated trains along random track segments.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 50);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="relative w-full overflow-hidden rounded-lg border border-border bg-[#040810]" style={{ height }}>
      {/* Grid backdrop */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 500 450" preserveAspectRatio="xMidYMid meet">
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
          </pattern>
          <radialGradient id="india-fill" cx="50%" cy="40%">
            <stop offset="0%" stopColor="rgba(59,130,246,0.10)" />
            <stop offset="100%" stopColor="rgba(59,130,246,0.02)" />
          </radialGradient>
          <filter id="glow"><feGaussianBlur stdDeviation="2" /></filter>
        </defs>

        <rect width="500" height="450" fill="url(#grid)" />

        {/* India outline */}
        <path d={INDIA_PATH} fill="url(#india-fill)" stroke="rgba(59,130,246,0.35)" strokeWidth="1.2" />

        {/* Risk zones */}
        {L.risk && RISK_ZONES.map((z, i) => {
          const c = z.tone === "critical" ? "#FF4D4F" : "#FFB020";
          return (
            <g key={i}>
              <circle cx={z.x} cy={z.y} r={z.r} fill={c} opacity="0.08" />
              <circle cx={z.x} cy={z.y} r={z.r * 0.6} fill={c} opacity="0.12" />
            </g>
          );
        })}

        {/* Tracks */}
        {L.tracks && TRACKS.map(([a, b], i) => {
          const sa = STATIONS[a], sb = STATIONS[b];
          return (
            <line key={i} x1={sa.x} y1={sa.y} x2={sb.x} y2={sb.y}
              stroke="rgba(148,163,184,0.25)" strokeWidth="0.8" />
          );
        })}

        {/* Animated train flow on key routes */}
        {L.trains && TRACKS.slice(0, 12).map(([a, b], i) => {
          const sa = STATIONS[a], sb = STATIONS[b];
          return (
            <line key={`f-${i}`} x1={sa.x} y1={sa.y} x2={sb.x} y2={sb.y}
              stroke="#3B82F6" strokeWidth="0.8" className="dash-flow" opacity="0.6" />
          );
        })}

        {/* Stations */}
        {L.stations && STATIONS.map((s, i) => {
          const isHub = s.type === "hub";
          const isMajor = s.type === "major";
          const r = isHub ? 3.5 : isMajor ? 2.5 : 1.8;
          return (
            <g key={i}>
              {isHub && (
                <circle cx={s.x} cy={s.y} r={r * 3} fill="#3B82F6" opacity="0.15">
                  <animate attributeName="r" values={`${r*2};${r*4};${r*2}`} dur="2.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.25;0;0.25" dur="2.5s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={s.x} cy={s.y} r={r} fill={isHub ? "#3B82F6" : "#94A3B8"} stroke="#0D1525" strokeWidth="0.6" />
              {!compact && isHub && (
                <text x={s.x + 6} y={s.y - 3} fill="#94A3B8" fontSize="6" fontFamily="ui-monospace">{s.name}</text>
              )}
            </g>
          );
        })}

        {/* Trains moving along track segments */}
        {L.trains && TRACKS.slice(0, 18).map(([a, b], i) => {
          const sa = STATIONS[a], sb = STATIONS[b];
          const t = ((tick * 0.6 + i * 17) % 100) / 100;
          const x = sa.x + (sb.x - sa.x) * t;
          const y = sa.y + (sb.y - sa.y) * t;
          const c = i % 7 === 0 ? "#FF4D4F" : i % 5 === 0 ? "#FFB020" : "#22C55E";
          return (
            <g key={`t-${i}`}>
              <circle cx={x} cy={y} r="2" fill={c} style={{ filter: `drop-shadow(0 0 4px ${c})` }} />
            </g>
          );
        })}

        {/* Incidents */}
        {L.incidents && INCIDENTS.map((it, i) => (
          <g key={i}>
            <circle cx={it.x} cy={it.y} r="5" fill="#FF4D4F" opacity="0.3">
              <animate attributeName="r" values="3;9;3" dur="1.4s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="1.4s" repeatCount="indefinite" />
            </circle>
            <circle cx={it.x} cy={it.y} r="2.5" fill="#FF4D4F" />
          </g>
        ))}
      </svg>

      {/* Legend overlay */}
      {!compact && (
        <div className="absolute bottom-3 left-3 flex flex-wrap gap-3 rounded-md border border-border bg-background/70 backdrop-blur px-3 py-2 text-[10px] text-muted-foreground">
          <Dot c="#22C55E" /> Low Risk
          <Dot c="#FFB020" /> Medium
          <Dot c="#FF4D4F" /> Critical
          <Dot c="#3B82F6" /> Hub
          <Dot c="#94A3B8" /> Station
        </div>
      )}
      <div className="absolute top-3 right-3 flex items-center gap-2 rounded-md border border-border bg-background/70 backdrop-blur px-2.5 py-1 text-[10px] font-mono">
        <span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />
        LIVE • IST {new Date().toLocaleTimeString("en-IN", { hour12: false })}
      </div>
    </div>
  );
}

function Dot({ c }: { c: string }) {
  return <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full" style={{ background: c, boxShadow: `0 0 6px ${c}` }} /></span>;
}
