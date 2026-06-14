import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, Gauge, Bar } from "@/components/panels";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Sparkles } from "lucide-react";
import { useEffect, useState, useRef, useCallback } from "react";
import { API_BASE } from "@/hooks/use-prahari-api";

export const Route = createFileRoute("/ccrs")({
  head: () => ({ meta: [{ title: "CCRS Risk Center — PRAHARI" }, { name: "description", content: "Composite Collision Risk Score per train." }] }),
  component: CCRS,
});

type RiskData = {
  train_id: string;
  route: string;
  ccrs: number;
  risk_level: string;
  recommended_action: string;
  breakdown: {
    crew_fatigue: number;
    infra_risk_score: number;
    cyber_risk_score: number;
    public_report_risk: number;
  };
  contribution_percent: {
    crew_fatigue: number;
    infra_risk: number;
    cyber_risk: number;
    operational: number;
  };
};

import { collection, query, where, onSnapshot } from "firebase/firestore";
import { db } from "../lib/firebase";

function CCRS() {
  const [trainId, setTrainId] = useState("12627");
  const [risk, setRisk] = useState<RiskData | null>(null);
  const [trend, setTrend] = useState<{ t: number; v: number }[]>([]);
  const tickRef = useRef(0);

  useEffect(() => {
    // Reset trend when train changes
    setTrend([]);
    tickRef.current = 0;

    const q = query(collection(db, "ccrs_scores"), where("trainId", "==", trainId));
    const unsub = onSnapshot(q, (snapshot) => {
      if (!snapshot.empty) {
        const doc = snapshot.docs[0];
        const data = doc.data();
        
        // Map simplified seed data to expected RiskData structure
        const mappedData: RiskData = {
          train_id: data.trainId,
          route: "SBC-NDLS",
          ccrs: data.ccrs || 0,
          risk_level: data.riskLevel || "Normal",
          recommended_action: data.ccrs >= 75 ? "Halt train immediately" : "Monitor closely",
          breakdown: {
            crew_fatigue: data.crewRisk || 0,
            infra_risk_score: data.trackRisk || 0,
            cyber_risk_score: data.cyberRisk || 0,
            public_report_risk: 0
          },
          contribution_percent: {
            crew_fatigue: data.crewRisk || 0,
            infra_risk: data.trackRisk || 0,
            cyber_risk: data.cyberRisk || 0,
            operational: data.operationalRisk || 0
          }
        };

        setRisk(mappedData);

        // Accumulate trend points
        tickRef.current += 1;
        setTrend(prev => {
          const next = [...prev, { t: tickRef.current, v: mappedData.ccrs }];
          return next.length > 24 ? next.slice(-24) : next;
        });
      } else {
        setRisk(null);
      }
    });

    return () => unsub();
  }, [trainId]);

  const ccrs = risk?.ccrs ?? 0;
  const level = risk?.risk_level ?? "Safe";
  const tone = ccrs >= 75 ? "critical" : ccrs >= 55 ? "warning" : ccrs >= 30 ? "info" : "success";
  const label = level.toUpperCase();

  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

  // Risk contributors from live breakdown
  const contributors = risk ? [
    { l: "Crew Fatigue", v: Math.round(risk.contribution_percent.crew_fatigue), tone: "warning" as const },
    { l: "Track Health", v: Math.round(risk.contribution_percent.infra_risk), tone: "info" as const },
    { l: "Cyber Risk", v: Math.round(risk.contribution_percent.cyber_risk), tone: "purple" as const },
    { l: "Operational", v: Math.round(risk.contribution_percent.operational), tone: "success" as const },
  ] : [
    { l: "Crew Fatigue", v: 0, tone: "warning" as const },
    { l: "Track Health", v: 0, tone: "info" as const },
    { l: "Cyber Risk", v: 0, tone: "purple" as const },
    { l: "Operational", v: 0, tone: "success" as const },
  ];

  // Probability and time-to-critical derived from CCRS
  const probability = ccrs >= 75 ? `${Math.min(99, Math.round(ccrs))}%` : ccrs >= 55 ? `${Math.round(ccrs * 0.8)}%` : `${Math.round(ccrs * 0.5)}%`;
  const timeToCritical = ccrs >= 75 ? "< 15 min" : ccrs >= 55 ? "~45 min" : "> 2 hrs";

  return (
    <AppShell title="CCRS Risk Center" subtitle="Comprehensive Collision Risk Score">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Select Train</span>
        <select
          className="rounded-md bg-surface border border-border px-3 py-1.5 text-[12px] min-w-[280px]"
          value={trainId}
          onChange={(e) => setTrainId(e.target.value)}
        >
          <option value="12627">12627 — Chennai Central SF Express</option>
          <option value="12651">12651 — Sampark Kranti Express</option>
          <option value="12711">12711 — Pinakini Express</option>
          <option value="16317">16317 — Kochuveli Express</option>
          <option value="12621">12621 — Tamil Nadu Express</option>
          <option value="12609">12609 — Chennai Express</option>
          <option value="16723">16723 — Anantapuri Express</option>
          <option value="12693">12693 — Pearl City Express</option>
        </select>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Live CCRS Score" subtitle={`Updated ${timeStr} IST`}>
          <div className="grid place-items-center py-6">
            <Gauge value={Math.round(ccrs)} max={100} tone={tone as any} label={label} size={260} />
          </div>
          <div className="grid grid-cols-3 gap-3 mt-2 text-center text-[11px]">
            <Stat l="Probability of Incident" v={probability} tone={ccrs >= 75 ? "text-critical" : "text-warning"} />
            <Stat l="Time to Critical" v={timeToCritical} tone="text-warning" />
            <Stat l="Last Updated" v={timeStr.substring(0, 5)} tone="text-foreground" />
          </div>
        </Panel>

        <Panel title="Risk Trend" subtitle="Live updates">
          <div className="h-[280px]">
            <ResponsiveContainer>
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="rt" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF4D4F" stopOpacity={0.6} />
                    <stop offset="100%" stopColor="#FF4D4F" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="t" stroke="#475569" fontSize={10} />
                <YAxis stroke="#475569" fontSize={10} />
                <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8 }} />
                <Area type="monotone" dataKey="v" stroke="#FF4D4F" strokeWidth={2} fill="url(#rt)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Risk Contributors">
          {contributors.map((c) => (
            <div key={c.l} className="mb-4 last:mb-0">
              <div className="flex justify-between text-[12px] mb-1.5">
                <span className="text-muted-foreground">{c.l}</span>
                <span className="text-mono font-semibold">{c.v}%</span>
              </div>
              <Bar value={c.v} tone={c.tone} />
            </div>
          ))}
        </Panel>

        <Panel title="Risk Details">
          <ul className="text-[12px] space-y-2.5">
            <Row l="Risk Level" r={label} rc={ccrs >= 75 ? "text-critical" : ccrs >= 55 ? "text-warning" : "text-success"} />
            <Row l="Probability of Incident" r={probability} />
            <Row l="Time to Critical" r={timeToCritical} rc="text-warning" />
            <Row l="Route" r={risk?.route ?? "—"} />
            <Row l="Recommended Speed" r={ccrs >= 75 ? "20 km/h" : ccrs >= 55 ? "40 km/h" : "Normal"} rc={ccrs >= 55 ? "text-warning" : "text-foreground"} />
            <Row l="Last Updated" r={`${timeStr} IST`} />
          </ul>
        </Panel>
      </div>

      <Panel title="AI Explainability" className="mt-4"
        action={<span className="inline-flex items-center gap-1 text-[11px] text-purple"><Sparkles className="h-3.5 w-3.5" />Generated by PRAHARI AI</span>}>
        <div className="rounded-md border border-purple/20 bg-purple/5 p-4 text-[12px] leading-relaxed">
          <p>
            {risk?.recommended_action ? (
              <>
                <span className={`font-semibold ${ccrs >= 75 ? "text-critical" : ccrs >= 55 ? "text-warning" : "text-success"}`}>
                  {level} risk detected for Train {trainId}.
                </span>{" "}
                {risk.recommended_action}{" "}
                Pattern analysis indicates the dominant risk factor is{" "}
                {contributors.reduce((a, b) => (a.v > b.v ? a : b)).l.toLowerCase()}{" "}
                contributing {contributors.reduce((a, b) => (a.v > b.v ? a : b)).v}% of the composite score.
                Route: {risk.route}.
              </>
            ) : (
              <span className="text-muted-foreground">Loading AI analysis...</span>
            )}
          </p>
        </div>
      </Panel>
    </AppShell>
  );
}
function Stat({ l, v, tone }: { l: string; v: string; tone: string }) {
  return (
    <div className="rounded-md border border-border/60 bg-surface/60 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{l}</div>
      <div className={`text-mono text-base font-semibold ${tone}`}>{v}</div>
    </div>
  );
}
function Row({ l, r, rc = "text-foreground" }: { l: string; r: string; rc?: string }) {
  return (
    <li className="flex items-center justify-between border-b border-border/60 last:border-0 pb-2 last:pb-0">
      <span className="text-muted-foreground">{l}</span>
      <span className={`text-mono font-semibold ${rc}`}>{r}</span>
    </li>
  );
}
