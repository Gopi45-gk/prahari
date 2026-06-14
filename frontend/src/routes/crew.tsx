import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, Gauge } from "@/components/panels";
import { Video, Eye } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export const Route = createFileRoute("/crew")({
  head: () => ({ meta: [{ title: "Crew Intelligence — PRAHARI" }, { name: "description", content: "Loco Pilot monitoring and fatigue analysis." }] }),
  component: Crew,
});

type Alert = { t: string; time: string; tone: "critical" | "warning" };

function Crew() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [cai, setCai] = useState(0);
  const [fatigueScore, setFatigueScore] = useState(0);
  const [msEvents, setMsEvents] = useState(0);
  const [blinkRate, setBlinkRate] = useState(0);
  const [riskLevel, setRiskLevel] = useState("NORMAL");
  const [statusTone, setStatusTone] = useState("success");
  const [overlayImage, setOverlayImage] = useState<string | null>(null);
  
  // Extra detailed metrics
  const [hrv, setHrv] = useState(0);
  const [postureSway, setPostureSway] = useState("Normal");
  
  // Shift details
  const [dutyStartTime, setDutyStartTime] = useState("02:30 AM");
  const [dutyDuration, setDutyDuration] = useState("00h 00m");
  const [breakDuration, setBreakDuration] = useState("00h 00m");
  const [continuousDriving, setContinuousDriving] = useState("00h 00m");
  const [trainsDriven, setTrainsDriven] = useState(3);
  const [distanceCovered, setDistanceCovered] = useState("412 km");

  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    if (riskLevel === "CRITICAL") setStatusTone("critical");
    else if (riskLevel === "HIGH") setStatusTone("warning");
    else setStatusTone("success");
  }, [riskLevel]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    
    // Start webcam
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((s) => {
        stream = s;
        if (videoRef.current) {
          videoRef.current.srcObject = s;
        }
      })
      .catch((err) => console.error("Webcam error:", err));

    // Connect WebSocket
    const ws = new WebSocket("ws://localhost:8001/ws/crew");
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setCai(data.cai ?? 0);
        setFatigueScore(data.fatigue_score ?? 0);
        setMsEvents(data.microsleep_events ?? 0);
        setBlinkRate(data.blink_rate ?? 0);
        setRiskLevel(data.risk_level ?? "NORMAL");
        
        if (data.hrv !== undefined) setHrv(data.hrv);
        if (data.posture_sway !== undefined) setPostureSway(data.posture_sway);
        
        if (data.duty_duration) setDutyDuration(data.duty_duration);
        if (data.continuous_driving) setContinuousDriving(data.continuous_driving);
        
        if (data.alerts && Array.isArray(data.alerts)) {
          setAlerts(data.alerts);
        }
        if (data.image) {
          setOverlayImage(data.image);
        }
      } catch (e) {
        console.error(e);
      }
    };

    // Frame capture interval
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN && videoRef.current && canvasRef.current) {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        
        if (video.videoWidth > 0 && ctx) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const dataUrl = canvas.toDataURL("image/jpeg", 0.5);
          ws.send(dataUrl);
        }
      }
    }, 1000);

    return () => {
      clearInterval(interval);
      if (ws.readyState === WebSocket.OPEN) ws.close();
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <AppShell title="Crew Intelligence Center" subtitle="Loco Pilot Monitoring & Safety">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Select Loco Pilot</span>
          <select className="rounded-md bg-surface border border-border px-3 py-1.5 text-[12px] min-w-[260px]">
            <option>LP2001 — Ramesh Kumar</option>
          </select>
        </div>
        <div className={`flex items-center gap-2 rounded-md border border-${statusTone}/30 bg-${statusTone}/10 px-3 py-1.5`}>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Overall Status</span>
          <span className={`text-[12px] font-bold text-${statusTone}`}>{riskLevel}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Live Alertness Score" subtitle="Real-time eye tracking + behavior model">
          <div className="grid place-items-center py-4">
            <Gauge value={cai} max={100} tone={statusTone as "warning" | "info" | "critical" | "success"} label={riskLevel} size={240} />
          </div>
          <div className="text-center text-[11px] text-muted-foreground">Alert threshold: 60 — operator below safety floor</div>
        </Panel>

        <Panel title="Fatigue Analysis">
          <div className="space-y-3 text-[12px]">
            <Row l="Fatigue Score" r={`${fatigueScore} / 100`} rc={fatigueScore > 60 ? "text-critical" : "text-success"} />
            <Row l="Microsleep Events (last 1 hr)" r={msEvents.toString()} rc={msEvents > 0 ? "text-critical" : "text-success"} />
            <Row l="Blink Rate" r={`${blinkRate} / min`} rc="text-warning" sub={blinkRate < 10 ? "Low" : blinkRate > 25 ? "High" : "Normal"} />
            <Row l="HRV (heart rate var.)" r={`${hrv} ms`} rc={hrv < 20 ? "text-warning" : "text-success"} />
            <Row l="Posture Sway" r={postureSway} rc={postureSway === "High" ? "text-warning" : "text-success"} />
            <Row l="Hours on Duty" r={dutyDuration} />
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Shift Details">
          <div className="grid grid-cols-2 gap-3 text-[12px]">
            <Tile l="Duty Start Time" v={dutyStartTime} />
            <Tile l="Duty Duration" v={dutyDuration} />
            <Tile l="Break Duration" v={breakDuration} />
            <Tile l="Continuous Driving" v={continuousDriving} tone={continuousDriving > "02h 00m" ? "text-warning" : "text-foreground"} />
            <Tile l="Trains Driven" v={trainsDriven.toString()} />
            <Tile l="Distance Covered" v={distanceCovered} />
          </div>
        </Panel>

        <Panel title="Live Camera Feed" subtitle="Cabin Camera — LP2001"
          action={<span className="inline-flex items-center gap-1 text-[10px] text-critical"><span className="h-1.5 w-1.5 rounded-full bg-critical pulse-dot" />REC</span>}>
          <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border bg-gradient-to-br from-black to-[#0A1220]">
            <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover z-10 opacity-70" autoPlay playsInline muted />
            {overlayImage && <img src={overlayImage} className="absolute inset-0 w-full h-full object-cover z-10" alt="ML Overlay" />}
            <canvas ref={canvasRef} className="hidden" />
            <div className="absolute inset-0 grid place-items-center">
              <div className="w-32 h-32 rounded-full bg-white/5 grid place-items-center">
                <Video className="h-12 w-12 text-muted-foreground/40" />
              </div>
            </div>
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_60%,rgba(255,77,79,0.12),transparent_60%)] z-20 pointer-events-none" />
            <div className="absolute top-3 left-3 text-[10px] font-mono text-muted-foreground z-20">CAM-01 • Cabin Front</div>
            <div className="absolute bottom-3 left-3 text-[10px] font-mono text-success z-20">EYE-TRACK ACTIVE</div>
            <div className="absolute bottom-3 right-3 text-[10px] font-mono text-muted-foreground z-20">LIVE DATA</div>
            <div className="absolute top-3 right-3 grid grid-cols-3 gap-1 z-20">
              {Array.from({length: 9}).map((_,i)=><span key={i} className="h-1 w-1 rounded-full bg-success/60" />)}
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Critical Alerts" className="mt-4">
        {alerts.length === 0 ? (
          <div className="text-center text-muted-foreground text-[12px] py-4">No critical alerts detected</div>
        ) : (
          <ul className="space-y-2 text-[12px]">
            {alerts.map((a, i) => (
              <li key={i} className={`flex items-center gap-3 rounded-md border bg-surface/40 px-3 py-2 ${a.tone === "critical" ? "border-critical/30" : "border-warning/30"}`}>
                <Eye className={`h-4 w-4 ${a.tone === "critical" ? "text-critical" : "text-warning"}`} />
                <span className="flex-1">{a.t}</span>
                <span className="text-mono text-[11px] text-muted-foreground">{a.time}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </AppShell>
  );
}

function Row({ l, r, rc = "text-foreground", sub }: { l: string; r: string; rc?: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 pb-2 last:border-0">
      <span className="text-muted-foreground">{l}</span>
      <div className="text-right"><span className={`text-mono font-semibold ${rc}`}>{r}</span>{sub && <span className="ml-2 text-[10px] text-muted-foreground">({sub})</span>}</div>
    </div>
  );
}

function Tile({ l, v, tone = "text-foreground" }: { l: string; v: string; tone?: string }) {
  return (
    <div className="rounded-md border border-border/60 bg-surface/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{l}</div>
      <div className={`text-mono text-lg font-semibold ${tone}`}>{v}</div>
    </div>
  );
}
