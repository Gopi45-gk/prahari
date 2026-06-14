import { useEffect, useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { usePrahariQuery } from "@/hooks/use-prahari-api";
import { ShieldCheck, ShieldAlert, Activity, Cpu, AlertTriangle } from "lucide-react";

// Real-world coordinates for STATIONS mapping
const STATIONS: Record<string, [number, number]> = {
  "New Delhi": [28.6139, 77.2090],
  "Mumbai": [19.0760, 72.8777],
  "Chennai": [13.0827, 80.2707],
  "Kolkata": [22.5726, 88.3639],
  "Bengaluru": [12.9716, 77.5946],
  "Hyderabad": [17.3850, 78.4867],
  "Ahmedabad": [23.0225, 72.5714],
  "Jaipur": [26.9124, 75.7873],
  "Lucknow": [26.8467, 80.9462],
  "Patna": [25.5941, 85.1376],
  "Bhopal": [23.2599, 77.4126],
  "Nagpur": [21.1458, 79.0882],
  "Pune": [18.5204, 73.8567],
  "Kochi": [9.9312, 76.2673],
  "Vizag": [17.6868, 83.2185],
  "Bhubaneswar": [20.2961, 85.8245],
  "Indore": [22.7196, 75.8577],
  "Surat": [21.1702, 72.8311],
  "Coimbatore": [11.0168, 76.9558],
  "Guwahati": [26.1445, 91.7362],
};

const ROUTES: [string, string][] = [
  ["New Delhi", "Mumbai"], ["New Delhi", "Chennai"], ["New Delhi", "Kolkata"],
  ["New Delhi", "Lucknow"], ["New Delhi", "Jaipur"], ["New Delhi", "Patna"],
  ["Mumbai", "Bengaluru"], ["Mumbai", "Hyderabad"], ["Mumbai", "Ahmedabad"],
  ["Mumbai", "Nagpur"], ["Mumbai", "Pune"], ["Chennai", "Bengaluru"],
  ["Chennai", "Hyderabad"], ["Chennai", "Vizag"], ["Chennai", "Kochi"],
  ["Chennai", "Coimbatore"], ["Kolkata", "Patna"], ["Kolkata", "Bhubaneswar"],
  ["Kolkata", "Guwahati"], ["Bengaluru", "Hyderabad"], ["Bengaluru", "Kochi"],
  ["Hyderabad", "Nagpur"], ["Hyderabad", "Vizag"], ["Ahmedabad", "Bhopal"],
  ["Jaipur", "Lucknow"], ["Jaipur", "Bhopal"], ["Lucknow", "Bhopal"],
  ["Bhopal", "Nagpur"], ["Nagpur", "Bhubaneswar"], ["Nagpur", "Vizag"],
];

const RISK_ZONES = [
  { center: [23.2599, 77.4126] as [number, number], r: 80000, tone: "warning" },
  { center: [19.0760, 72.8777] as [number, number], r: 60000, tone: "critical" },
  { center: [25.5941, 85.1376] as [number, number], r: 50000, tone: "warning" },
];

const INCIDENTS = [
  { center: [24.2599, 76.4126] as [number, number], label: "Track Defect KM 142/7" },
  { center: [25.5941, 85.1376] as [number, number], label: "Signal Failure - Patna Yard" },
  { center: [21.1458, 79.0882] as [number, number], label: "Cyber Alert - Nagpur Sec" },
];

const createTrainIcon = (color: string) => {
  return L.divIcon({
    className: "custom-train-marker",
    html: `<div style="background:${color}; width: 22px; height: 22px; border-radius: 50%; box-shadow: 0 0 10px ${color}; border: 2px solid #040810; display:flex; align-items:center; justify-content:center; font-size: 12px; color: #fff;">🚆</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -11]
  });
};

const incidentIcon = L.divIcon({
  className: "custom-incident-marker",
  html: `<div style="background:#FF4D4F; width: 14px; height: 14px; border-radius: 50%; box-shadow: 0 0 12px #FF4D4F; border: 2px solid #040810; animation: pulse 1.5s infinite;"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
  popupAnchor: [0, -7]
});

// CSS injected to perfectly match the dark theme and animation
const mapStyles = `
  .leaflet-container {
    background-color: #040810 !important;
    font-family: inherit;
  }
  .leaflet-layer,
  .leaflet-control-zoom-in,
  .leaflet-control-zoom-out,
  .leaflet-control-attribution {
    filter: invert(100%) hue-rotate(180deg) brightness(85%) contrast(90%);
  }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(255, 77, 79, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0); }
  }
  .prahari-popup .leaflet-popup-content-wrapper {
    background: rgba(4, 8, 16, 0.9) !important;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.1);
    color: #e2e8f0;
    border-radius: 8px;
    padding: 0;
  }
  .prahari-popup .leaflet-popup-tip {
    background: rgba(4, 8, 16, 0.9) !important;
    border-top: 1px solid rgba(255,255,255,0.1);
    border-left: 1px solid rgba(255,255,255,0.1);
  }
  .prahari-popup .leaflet-popup-content {
    margin: 0;
    line-height: 1.4;
  }
`;

export default function LiveRailwayMapClient({
  showLayers = { trains: true, signals: true, stations: true, risk: true, incidents: true, weather: false, tracks: true },
  height = 460,
  compact = false,
}: {
  showLayers?: Partial<{ trains: boolean; signals: boolean; stations: boolean; risk: boolean; incidents: boolean; weather: boolean; tracks: boolean }>;
  height?: number;
  compact?: boolean;
}) {
  const { data: summary } = usePrahariQuery<any>("/api/dashboard-summary", 5000);
  
  const [tick, setTick] = useState(0);
  useEffect(() => {
    // Slower tick for a realistic train movement
    const id = setInterval(() => setTick(t => t + 1), 200);
    return () => clearInterval(id);
  }, []);

  const trains = useMemo(() => {
    if (!summary?.trains) return [];
    return summary.trains.map((train: any, i: number) => {
      const routeIdx = i % ROUTES.length;
      const [startCity, endCity] = ROUTES[routeIdx];
      const startNode = STATIONS[startCity];
      const endNode = STATIONS[endCity];
      
      const t = ((tick * 0.05 + i * 17) % 100) / 100; // Loops 0 to 1 smoothly
      const lat = startNode[0] + (endNode[0] - startNode[0]) * t;
      const lng = startNode[1] + (endNode[1] - startNode[1]) * t;

      let color = "#22C55E"; // Safe
      if (train.risk_level === "Warning" || train.risk_level === "Medium") color = "#FFB020";
      if (train.risk_level === "High") color = "#F97316";
      if (train.risk_level === "Critical") color = "#FF4D4F";

      return { ...train, lat, lng, color };
    });
  }, [summary?.trains, tick]);

  const L_SETTINGS = { trains: true, signals: true, stations: true, risk: true, incidents: true, weather: false, tracks: true, ...showLayers };

  return (
    <div className="relative w-full overflow-hidden rounded-lg border border-border bg-[#040810]" style={{ height }}>
      <style>{mapStyles}</style>
      
      <MapContainer 
        center={[22.9734, 78.6569]} 
        zoom={5} 
        style={{ width: "100%", height: "100%" }}
        zoomControl={false}
        attributionControl={false}
      >
        {/* Base OSM Layer */}
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        
        {/* OpenRailwayMap Overlay */}
        {L_SETTINGS.tracks && (
          <TileLayer
            url="https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"
            maxZoom={19}
          />
        )}

        {/* Risk Zones Heatmap */}
        {L_SETTINGS.risk && RISK_ZONES.map((zone, idx) => (
          <Circle
            key={idx}
            center={zone.center}
            radius={zone.r}
            pathOptions={{ 
              color: zone.tone === "critical" ? "#FF4D4F" : "#FFB020",
              fillColor: zone.tone === "critical" ? "#FF4D4F" : "#FFB020",
              fillOpacity: 0.15,
              weight: 1
            }}
          />
        ))}

        {/* Incident Markers */}
        {L_SETTINGS.incidents && INCIDENTS.map((inc, idx) => (
          <Marker key={`inc-${idx}`} position={inc.center} icon={incidentIcon}>
            <Popup className="prahari-popup">
              <div className="p-3 w-48">
                <div className="flex items-center gap-2 text-critical mb-2 font-semibold text-xs border-b border-white/10 pb-2">
                  <AlertTriangle className="h-4 w-4" />
                  <span>CRITICAL INCIDENT</span>
                </div>
                <div className="text-[11px] mb-2">{inc.label}</div>
                <div className="text-[9px] text-muted-foreground flex justify-between">
                  <span>Status: Pending</span>
                  <span>Dispatched: Yes</span>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Live Trains with Popups */}
        {L_SETTINGS.trains && trains.map((t: any, idx: number) => (
          <Marker 
            key={`train-${idx}`} 
            position={[t.lat, t.lng]} 
            icon={createTrainIcon(t.color)}
          >
            <Popup className="prahari-popup">
              <div className="p-3 w-64">
                <div className="flex justify-between items-start mb-3 border-b border-white/10 pb-2">
                  <div>
                    <div className="text-sm font-bold text-white">Train {t.train_id}</div>
                    <div className="text-[10px] text-muted-foreground">{t.route}</div>
                  </div>
                  <div className="px-2 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: t.color + "20", color: t.color, border: "1px solid " + t.color + "50" }}>
                    {t.risk_level.toUpperCase()}
                  </div>
                </div>

                <div className="space-y-2 text-[11px]">
                  <div className="flex justify-between items-center bg-white/5 px-2 py-1 rounded">
                    <span className="text-muted-foreground flex items-center gap-1"><Activity className="h-3 w-3"/> CCRS Score</span>
                    <span className="font-mono font-bold" style={{ color: t.color }}>{t.ccrs.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between items-center px-2 py-1">
                    <span className="text-muted-foreground flex items-center gap-1"><ShieldAlert className="h-3 w-3"/> Track Risk</span>
                    <span className="font-mono">{t.breakdown?.infra_risk_score.toFixed(1) ?? "--"}</span>
                  </div>
                  <div className="flex justify-between items-center px-2 py-1">
                    <span className="text-muted-foreground flex items-center gap-1"><Cpu className="h-3 w-3"/> Cyber Risk</span>
                    <span className="font-mono">{t.breakdown?.cyber_risk_score.toFixed(1) ?? "--"}</span>
                  </div>
                  <div className="flex justify-between items-center px-2 py-1">
                    <span className="text-muted-foreground flex items-center gap-1"><ShieldCheck className="h-3 w-3"/> Crew Alertness</span>
                    <span className="font-mono">{t.breakdown?.crew_fatigue.toFixed(1) ?? "--"}</span>
                  </div>
                </div>

                <div className="mt-3 text-[9px] text-muted-foreground pt-2 border-t border-white/10 text-right">
                  Last Updated: {new Date().toLocaleTimeString()}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* PRAHARI Map Overlays */}
      {!compact && (
        <div className="absolute bottom-3 left-3 flex flex-wrap gap-3 rounded-md border border-border bg-background/70 backdrop-blur px-3 py-2 text-[10px] text-muted-foreground z-[1000]">
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_6px_#22C55E]" /> Low Risk</span>
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-warning shadow-[0_0_6px_#FFB020]" /> Medium</span>
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-critical shadow-[0_0_6px_#FF4D4F]" /> Critical</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full border border-warning bg-warning/20" /> Risk Zone</span>
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-critical shadow-[0_0_6px_#FF4D4F] animate-pulse" /> Alert</span>
        </div>
      )}
      <div className="absolute top-3 right-3 flex items-center gap-2 rounded-md border border-border bg-background/70 backdrop-blur px-2.5 py-1 text-[10px] font-mono z-[1000]">
        <span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />
        LIVE • IST {new Date().toLocaleTimeString("en-IN", { hour12: false })}
      </div>
    </div>
  );
}
