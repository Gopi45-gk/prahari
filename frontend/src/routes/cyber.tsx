import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { collection, onSnapshot } from "firebase/firestore";
import { db } from "../lib/firebase";
import { Panel, Gauge } from "@/components/panels";
import { Server, Network, Cpu, ShieldCheck, Radio as RadioIcon } from "lucide-react";
import { useEffect, useState, useRef } from "react";

export const Route = createFileRoute("/cyber")({
  head: () => ({ meta: [{ title: "Cyber SOC — PRAHARI" }, { name: "description", content: "Railway OT/SCADA Security Operations Center." }] }),
  component: Cyber,
});

type CyberSnapshot = {
  avg_cyber_risk: number;
  anomalies_detected: number;
  threat_level: string;
  network_health: number;
  total_assets_scanned: number;
  assets: { asset_id: string; is_anomaly: boolean; cyber_risk_score: number }[];
};

type ThreatEvent = { time: string; tone: string; text: string };

function Cyber() {
  const [cyber, setCyber] = useState<CyberSnapshot>({
    avg_cyber_risk: 0, anomalies_detected: 0, threat_level: "LOW",
    network_health: 100, total_assets_scanned: 0, assets: [],
  });
  const [feed, setFeed] = useState<ThreatEvent[]>([]);
  const feedRef = useRef<ThreatEvent[]>([]);

  useEffect(() => {
    const unsub = onSnapshot(collection(db, "cyber_alerts"), (snapshot: any) => {
      if (snapshot.empty) return;
      
      const alerts = snapshot.docs.map((d: any) => d.data());
      const activeAlerts = alerts.filter((a: any) => a.status === "Active");
      
      let critical = 0;
      activeAlerts.forEach((a: any) => {
        if (a.severity === "Critical") critical++;
      });

      const avgRisk = activeAlerts.length > 0 ? (critical > 0 ? 85 : 55) : 10;
      const threatLevel = critical > 0 ? "CRITICAL" : activeAlerts.length > 0 ? "ELEVATED" : "LOW";

      setCyber({
        avg_cyber_risk: avgRisk,
        anomalies_detected: activeAlerts.length,
        threat_level: threatLevel,
        network_health: Math.max(0, 100 - avgRisk),
        total_assets_scanned: 412, // Mocked
        assets: alerts.map((a: any) => ({
          asset_id: a.alertId || "Unknown",
          is_anomaly: a.status === "Active",
          cyber_risk_score: a.severity === "Critical" ? 90 : 60
        }))
      });

      const now = new Date();
      const timeStr = now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
      const newEvents: ThreatEvent[] = [];

      activeAlerts.forEach((a: any) => {
        newEvents.push({
          time: timeStr,
          tone: a.severity === "Critical" ? "critical" : "warning",
          text: `[${a.alertId}] ${a.threatType}`
        });
      });

      feedRef.current = [...newEvents, ...feedRef.current].slice(0, 30);
      setFeed(feedRef.current);
    });

    return () => unsub();
  }, []);

  const threatVal = Math.round(cyber.avg_cyber_risk);
  const threatTone = threatVal > 60 ? "critical" : threatVal > 30 ? "warning" : "success";
  const threatLabel = cyber.threat_level;

  const nhVal = Math.round(cyber.network_health);
  const nhTone = nhVal >= 80 ? "success" : nhVal >= 50 ? "warning" : "critical";
  const nhLabel = nhVal >= 80 ? "SECURE" : nhVal >= 50 ? "DEGRADED" : "AT RISK";

  // Derive anomaly breakdown from assets
  const anomalyBreakdown = cyber.assets.reduce((acc, a) => {
    if (a.is_anomaly) acc.anomalous++;
    else acc.normal++;
    return acc;
  }, { anomalous: 0, normal: 0 });

  return (
    <AppShell title="Cyber Security Operations Center" subtitle="Railway OT / SCADA Security Monitoring">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Overall Threat Level">
          <div className="flex items-center gap-6 py-2">
            <Gauge value={threatVal} max={100} tone={threatTone as any} label={threatLabel} size={180} />
            <div className="space-y-2 text-[12px]">
              <Row l="Active Investigations" v={String(cyber.anomalies_detected)} tone={cyber.anomalies_detected > 0 ? "text-warning" : "text-success"} />
              <Row l="Assets Scanned" v={String(cyber.total_assets_scanned)} tone="text-success" />
              <Row l="Anomalies Detected" v={String(anomalyBreakdown.anomalous)} tone={anomalyBreakdown.anomalous > 0 ? "text-warning" : "text-success"} />
              <Row l="Critical Findings" v={String(anomalyBreakdown.anomalous)} tone={anomalyBreakdown.anomalous > 0 ? "text-critical" : "text-success"} />
            </div>
          </div>
        </Panel>

        <Panel title="Active Anomalies"
          action={<button className="text-[11px] text-info hover:underline">View All</button>}>
          <div className="text-mono text-5xl font-bold text-warning">{cyber.anomalies_detected}</div>
          <ul className="mt-3 space-y-1.5 text-[12px]">
            {cyber.assets.filter(a => a.is_anomaly).map((a) => (
              <li key={a.asset_id} className="flex justify-between border-b border-border/60 pb-1.5">
                <span>{a.asset_id} — Anomaly</span>
                <span className="text-mono">{a.cyber_risk_score}</span>
              </li>
            ))}
            {cyber.anomalies_detected === 0 && (
              <li className="flex justify-between border-b border-border/60 pb-1.5">
                <span>No anomalies detected</span>
                <span className="text-mono">0</span>
              </li>
            )}
          </ul>
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Network Health">
          <div className="grid place-items-center py-4">
            <Gauge value={nhVal} max={100} tone={nhTone as any} label={nhLabel} size={200} />
          </div>
        </Panel>

        <Panel title="Threat Intelligence Feed">
          <ul className="space-y-2 text-[12px] max-h-[260px] overflow-y-auto">
            {feed.map((f, i) => (
              <li key={i} className="flex items-start gap-2 border-b border-border/60 last:border-0 pb-2">
                <span className="text-mono text-[10px] text-muted-foreground w-10 mt-0.5">{f.time}</span>
                <span className={`h-1.5 w-1.5 rounded-full mt-2 ${f.tone==="critical"?"bg-critical":f.tone==="warning"?"bg-warning":"bg-info"}`} />
                <span className="flex-1">{f.text}</span>
              </li>
            ))}
            {feed.length === 0 && (
              <li className="text-center text-muted-foreground py-4">Waiting for data...</li>
            )}
          </ul>
        </Panel>
      </div>

      <Panel title="Network Map (OT)" subtitle="Operational Technology topology" className="mt-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 py-6">
          {([
            { l: "Control Center", Icon: Server, tone: "success" as const },
            { l: "SCADA Server", Icon: Cpu, tone: "success" as const },
            { l: "Field Device", Icon: ShieldCheck, tone: (cyber.anomalies_detected > 0 ? "warning" : "success") as "warning" | "success" },
            { l: "Sensor Network", Icon: RadioIcon, tone: "success" as const },
            { l: "Signal System", Icon: Network, tone: "success" as const },
          ]).map(({ l, Icon, tone }, i, arr) => (
            <div key={l} className="relative flex flex-col items-center">
              <div className={`relative grid h-16 w-16 place-items-center rounded-xl border bg-surface ${
                tone==="success"?"border-success/30 text-success glow-success":"border-warning/30 text-warning glow-warning"
              }`}>
                <Icon className="h-7 w-7" />
                <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-success pulse-dot" />
              </div>
              <div className="mt-2 text-[11px] text-center">{l}</div>
              {i < arr.length - 1 && (
                <div className="hidden md:block absolute top-8 left-[calc(50%+32px)] right-[-50%] h-px bg-gradient-to-r from-info/40 to-info/0" />
              )}
            </div>
          ))}
        </div>
      </Panel>
    </AppShell>
  );
}
function Row({ l, v, tone = "text-foreground" }: { l: string; v: string; tone?: string }) {
  return <div className="flex items-center justify-between gap-6"><span className="text-muted-foreground">{l}</span><span className={`text-mono font-semibold ${tone}`}>{v}</span></div>;
}
