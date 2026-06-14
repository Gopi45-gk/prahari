import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { KpiCard, Panel, StatusPill, Gauge, Bar } from "@/components/panels";
import { LiveRailwayMap as IndiaMap } from "@/components/live-railway-map";
import { Train, AlertOctagon, ShieldAlert, CheckCircle2, ArrowUpRight } from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { useEffect, useState, useRef } from "react";
import { collection, onSnapshot } from "firebase/firestore";
import { db } from "../lib/firebase";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Command Center — PRAHARI Authority" },
      { name: "description", content: "Real-time railway safety overview and operations command center." },
    ],
  }),
  component: Dashboard,
});

type AlertEvent = { time: string; t: string; text: string; tone: string };

function Dashboard() {
  const [summary, setSummary] = useState<any>(null);
  const [trendData, setTrendData] = useState<{ t: string; alerts: number; risk: number }[]>([]);
  const [liveFeed, setLiveFeed] = useState<AlertEvent[]>([]);
  const feedRef = useRef<AlertEvent[]>([]);
  const tickRef = useRef(0);

  useEffect(() => {
    // Setup listeners for all metrics
    const unsubCCRS = onSnapshot(collection(db, "ccrs_scores"), (ccrsSnap) => {
      const trains = ccrsSnap.docs.map(d => d.data());
      const active_trains = trains.length;
      const high_risk_trains = trains.filter(t => t.ccrs > 55).length;
      const avg_ccrs = active_trains > 0 ? trains.reduce((acc, t) => acc + (t.ccrs || 0), 0) / active_trains : 0;
      
      setSummary((prev: any) => ({
        ...prev,
        active_trains,
        high_risk_trains,
        avg_ccrs,
        trains: trains.sort((a,b) => b.ccrs - a.ccrs).slice(0, 5)
      }));

      // Generate live feed
      const ts = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
      const newEvents: AlertEvent[] = [];
      for (const train of trains) {
        if (train.riskLevel === "Critical") {
          newEvents.push({ time: ts, t: "CRIT", text: `Train ${train.trainId} — CCRS ${train.ccrs} — CRITICAL`, tone: "critical" });
        } else if (train.riskLevel === "High") {
          newEvents.push({ time: ts, t: "WARN", text: `Train ${train.trainId} — CCRS ${train.ccrs} — HIGH RISK`, tone: "warning" });
        }
      }
      if (newEvents.length === 0) {
        newEvents.push({ time: ts, t: "OK", text: `All ${active_trains} trains operating safely`, tone: "success" });
      }

      feedRef.current = [...newEvents, ...feedRef.current].slice(0, 30);
      setLiveFeed([...feedRef.current]);

      // Trend data
      tickRef.current += 1;
      setTrendData(prev => {
        const next = [...prev, { t: ts, alerts: high_risk_trains, risk: Math.round(avg_ccrs) }];
        return next.length > 24 ? next.slice(-24) : next;
      });
    });

    const unsubCyber = onSnapshot(collection(db, "cyber_alerts"), (snap) => {
      const alerts = snap.docs.map(d => d.data()).filter(a => a.status === "Active");
      setSummary((prev: any) => ({
        ...prev,
        cyber_threat_level: alerts.filter(a => a.severity === "Critical").length > 0 ? 80 : (alerts.length > 0 ? 50 : 10)
      }));
    });

    const unsubHazards = onSnapshot(collection(db, "hazard_reports"), (snap) => {
      const reports = snap.docs.map(d => d.data()).filter(r => r.status === "Pending");
      setSummary((prev: any) => ({ ...prev, open_reports: reports.length }));
    });

    const unsubTrack = onSnapshot(collection(db, "track_health"), (snap) => {
      const tracks = snap.docs.map(d => d.data());
      setSummary((prev: any) => ({
        ...prev,
        critical_track_segments: tracks.filter(t => t.status === "Critical").length,
        avg_infra_risk: tracks.length > 0 ? tracks.reduce((acc, t) => acc + (100 - (t.healthScore || 0)), 0) / tracks.length : 0
      }));
    });

    return () => {
      unsubCCRS();
      unsubCyber();
      unsubHazards();
      unsubTrack();
    };
  }, []);

  const s = summary;
  const systemHealth = s ? Math.round(100 - (s.critical_alerts / Math.max(s.active_trains, 1)) * 100) : 98;

  // CCRS overview gauge
  const avgCcrs = s?.avg_ccrs ?? 0;
  const ccrsTone = avgCcrs >= 75 ? "critical" : avgCcrs >= 55 ? "warning" : avgCcrs >= 30 ? "info" : "success";
  const ccrsLabel = avgCcrs >= 75 ? "CRITICAL" : avgCcrs >= 55 ? "HIGH" : avgCcrs >= 30 ? "ELEVATED" : "SAFE";

  // Bottom bar values
  const crewFatigueRisk = s?.crew_fatigue_risk ?? 0;
  const cyberThreat = s?.cyber_threat_level ?? 0;
  const trackHealth = s?.track_sensor_health ?? 91;
  const signalAnomalies = s?.critical_alerts ?? 0;

  return (
    <AppShell title="Command Center" subtitle="Real-time Railway Safety Overview">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard label="Active Trains" value={s ? s.active_trains.toLocaleString() : "—"} tone="info" icon={<Train className="h-4 w-4" />} delta={{ value: "Live from API", up: true }} />
        <KpiCard label="Critical Alerts" value={s ? String(s.critical_alerts) : "—"} tone="critical" icon={<AlertOctagon className="h-4 w-4" />} footer={s ? `${s.open_reports} open reports` : ""} />
        <KpiCard label="High Risk Trains" value={s ? String(s.high_risk_trains) : "—"} tone="warning" icon={<ShieldAlert className="h-4 w-4" />} footer="View all" />
        <KpiCard label="System Health" value={`${systemHealth}%`} tone="success" icon={<CheckCircle2 className="h-4 w-4" />} footer="All Systems Operational" />
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Panel title="Live Network Overview" subtitle="Real-time Train & Risk Map" className="xl:col-span-2"
          action={<span className="text-[10px] font-mono text-muted-foreground">LIVE</span>}>
          <IndiaMap height={420} />
        </Panel>

        <div className="space-y-4">
          <Panel title="Today's Summary">
            <ul className="text-[12px] space-y-2.5">
              {[
                { l: "Total Alerts", v: s ? s.critical_alerts + s.high_risk_trains + s.open_reports : 0, tone: "text-foreground" },
                { l: "Resolved", v: s ? Math.max(0, (s.critical_alerts + s.high_risk_trains) - s.critical_alerts) : 0, tone: "text-success" },
                { l: "Pending", v: s?.open_reports ?? 0, tone: "text-warning" },
                { l: "Critical Segments", v: s?.critical_track_segments ?? 0, tone: "text-critical" },
                { l: "High Risk Trains", v: s?.high_risk_trains ?? 0, tone: "text-warning" },
              ].map((r) => (
                <li key={r.l} className="flex items-center justify-between border-b border-border/60 last:border-0 pb-2 last:pb-0">
                  <span className="text-muted-foreground">{r.l}</span>
                  <span className={`text-mono font-semibold ${r.tone}`}>{r.v}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="CCRS Overview" subtitle="Composite Collision Risk Score">
            <div className="grid place-items-center py-2">
              <Gauge value={Math.round(avgCcrs)} max={100} tone={ccrsTone as any} label={ccrsLabel} size={160} />
            </div>
            <div className="text-[11px] text-center text-muted-foreground">Average across active fleet</div>
          </Panel>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Panel title="Risk & Alert Trend" subtitle="Live updates" className="xl:col-span-2">
          <div className="h-56">
            <ResponsiveContainer>
              <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF4D4F" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#FF4D4F" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="t" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="alerts" stroke="#FF4D4F" fill="url(#ga)" strokeWidth={2} />
                <Area type="monotone" dataKey="risk" stroke="#3B82F6" fill="url(#gb)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Live Alert Feed" subtitle="Streaming"
          action={<span className="inline-flex items-center gap-1 text-[10px] text-success"><span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />LIVE</span>}>
          <ul className="space-y-2 max-h-[230px] overflow-y-auto pr-1">
            {liveFeed.map((f, i) => (
              <li key={i} className="flex items-start gap-3 rounded-md border border-border/60 bg-surface/60 px-3 py-2">
                <StatusPill status={f.t === "CRIT" ? "Critical" : f.t === "WARN" ? "Pending" : f.t === "OK" ? "Resolved" : "Active"} />
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-mono text-muted-foreground">{f.time}</div>
                  <div className="text-[12px] truncate">{f.text}</div>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              </li>
            ))}
            {liveFeed.length === 0 && (
              <li className="text-center text-muted-foreground text-[12px] py-4">Waiting for data...</li>
            )}
          </ul>
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { l: "Crew Fatigue Risk", v: Math.round(crewFatigueRisk), tone: "warning" as const },
          { l: "Signal Anomalies", v: signalAnomalies, tone: "info" as const },
          { l: "Track Sensor Health", v: Math.round(trackHealth), tone: "success" as const },
          { l: "Cyber Threat Level", v: Math.round(cyberThreat), tone: "critical" as const },
        ].map((s) => (
          <Panel key={s.l}>
            <div className="flex items-center justify-between text-[11px] text-muted-foreground uppercase tracking-wider">
              <span>{s.l}</span>
              <span className="text-mono text-foreground">{s.v}%</span>
            </div>
            <div className="mt-3"><Bar value={s.v} tone={s.tone} /></div>
          </Panel>
        ))}
      </div>
    </AppShell>
  );
}
