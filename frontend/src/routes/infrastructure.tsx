import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, Gauge, Bar } from "@/components/panels";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, AreaChart, Area } from "recharts";
import { useEffect, useState, useRef } from "react";

export const Route = createFileRoute("/infrastructure")({
  head: () => ({ meta: [{ title: "Infrastructure Health — PRAHARI" }, { name: "description", content: "Track, bridge and asset health monitoring." }] }),
  component: Infra,
});

type TrackSnapshot = {
  track_health_score: number;
  avg_vibration: number;
  avg_temperature: number;
  avg_stress: number;
  avg_wear: number;
  avg_infra_risk: number;
  critical_segments: number;
  warning_segments: number;
  safe_segments: number;
  total_segments: number;
};

function Infra() {
  const [health, setHealth] = useState<TrackSnapshot>({
    track_health_score: 0, avg_vibration: 0, avg_temperature: 0,
    avg_stress: 0, avg_wear: 0, avg_infra_risk: 0,
    critical_segments: 0, warning_segments: 0, safe_segments: 0, total_segments: 0,
  });

  const [trend, setTrend] = useState<{t: number, v: number}[]>([]);

  useEffect(() => {
    let tick = 0;
    const { collection, onSnapshot } = require("firebase/firestore");
    const { db } = require("../lib/firebase");

    const unsub = onSnapshot(collection(db, "track_health"), (snapshot: any) => {
      if (snapshot.empty) return;
      const tracks = snapshot.docs.map((d: any) => d.data());
      const total = tracks.length;
      let critical = 0, warning = 0, safe = 0, sumHealth = 0;

      tracks.forEach((t: any) => {
        sumHealth += t.healthScore || 0;
        if (t.status === "Critical") critical++;
        else if (t.status === "Warning") warning++;
        else safe++;
      });

      const avgHealth = sumHealth / total;
      
      setHealth({
        track_health_score: Math.round(avgHealth),
        avg_vibration: 2.1,
        avg_temperature: 32,
        avg_stress: 45,
        avg_wear: 15,
        avg_infra_risk: 100 - avgHealth,
        critical_segments: critical,
        warning_segments: warning,
        safe_segments: safe,
        total_segments: total,
      });

      tick++;
      setTrend(prev => {
        const next = [...prev, { t: tick, v: avgHealth }];
        return next.length > 20 ? next.slice(-20) : next;
      });
    });

    return () => unsub();
  }, []);

  const hs = health.track_health_score;
  const hsTone = hs >= 70 ? "success" : hs >= 40 ? "warning" : "critical";
  const hsLabel = hs >= 70 ? "HEALTHY" : hs >= 40 ? "HIGH RISK" : "CRITICAL";

  // Derive parameter percentages from raw values (normalize to 0-100 range)
  const params: [string, number, string][] = [
    ["Track Geometry", Math.round(Math.min(100, health.avg_stress)), health.avg_stress > 60 ? "warning" : "success"],
    ["Wear & Tear", Math.round(Math.min(100, health.avg_wear * 5)), health.avg_wear > 10 ? "warning" : "info"],
    ["Vibration", Math.round(Math.min(100, health.avg_vibration * 40)), health.avg_vibration > 2 ? "warning" : "success"],
    ["Temperature", Math.round(Math.min(100, (health.avg_temperature / 60) * 100)), health.avg_temperature > 45 ? "warning" : "info"],
    ["Infrastructure Risk", Math.round(health.avg_infra_risk), health.avg_infra_risk > 50 ? "warning" : "success"],
    ["Safe Segments", Math.round((health.safe_segments / Math.max(health.total_segments, 1)) * 100), "success"],
  ];

  return (
    <AppShell title="Infrastructure Health Center" subtitle="Track, Bridge & Asset Monitoring">
      <div className="flex flex-wrap items-center gap-2 mb-4 text-[12px]">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Section</span>
        <select className="rounded-md bg-surface border border-border px-3 py-1.5"><option>KM 142/0 — KM 143/0</option></select>
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider ml-2">Asset</span>
        <select className="rounded-md bg-surface border border-border px-3 py-1.5"><option>Track</option></select>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Track Health Index">
          <div className="grid place-items-center py-4">
            <Gauge value={Math.round(hs)} max={100} tone={hsTone as "warning" | "info" | "critical" | "success"} label={hsLabel} size={220} />
          </div>
        </Panel>

        <Panel title="Parameters">
          {params.map(([l, v, t]) => (
            <div key={l as string} className="mb-3">
              <div className="flex justify-between text-[12px] mb-1.5"><span className="text-muted-foreground">{l}</span><span className="text-mono">{v}%</span></div>
              <Bar value={v as number} tone={t as never} />
            </div>
          ))}
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Vibration Trend" subtitle="Live updates every 5s">
          <div className="h-56">
            <ResponsiveContainer>
              <AreaChart data={trend}>
                <defs><linearGradient id="vg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#FFB020" stopOpacity={0.5} /><stop offset="100%" stopColor="#FFB020" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="t" stroke="#475569" fontSize={10} />
                <YAxis stroke="#475569" fontSize={10} />
                <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)" }} />
                <Area type="monotone" dataKey="v" stroke="#FFB020" fill="url(#vg)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Temperature Trend (°C)" subtitle="Rail temperature">
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={trend}>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="t" stroke="#475569" fontSize={10} />
                <YAxis stroke="#475569" fontSize={10} />
                <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)" }} />
                <Line type="monotone" dataKey="v" stroke="#3B82F6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ["Active Sensors", String(health.total_segments), "text-info"],
          ["Sensors Degraded", String(health.warning_segments), "text-warning"],
          ["Bridges Monitored", "94", "text-foreground"],
          ["Critical Sections", String(health.critical_segments), "text-critical"],
        ].map(([l, v, c]) => (
          <Panel key={l}>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{l}</div>
            <div className={`text-mono text-2xl font-bold ${c}`}>{v}</div>
          </Panel>
        ))}
      </div>
    </AppShell>
  );
}
