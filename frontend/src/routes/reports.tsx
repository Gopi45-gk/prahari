import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panels";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell, Legend } from "recharts";

export const Route = createFileRoute("/reports")({
  head: () => ({ meta: [{ title: "Executive Dashboard — PRAHARI" }, { name: "description", content: "Strategic overview for leadership." }] }),
  component: Reports,
});

const trend30 = Array.from({ length: 30 }, (_, i) => ({ d: i + 1, score: 70 + Math.round(Math.sin(i/3)*8 + i*0.3) }));
const dist = [
  { name: "Low", value: 45, color: "#22C55E" },
  { name: "Medium", value: 30, color: "#FFB020" },
  { name: "High", value: 15, color: "#FF4D4F" },
  { name: "Critical", value: 10, color: "#8B5CF6" },
];

function Reports() {
  return (
    <AppShell title="Executive Dashboard" subtitle="Strategic Overview for Leadership"
      actions={
        <div className="hidden md:flex items-center gap-1 rounded-md border border-border bg-surface p-0.5 text-[11px]">
          {["Today","7d","30d","90d"].map((p, i) => (
            <button key={p} className={`px-2.5 py-1 rounded ${i===2 ? "bg-info text-white" : "text-muted-foreground hover:text-foreground"}`}>{p}</button>
          ))}
        </div>
      }>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <BigStat l="Safety Score" v="88" tone="success" delta="+6% from last month" />
        <BigStat l="Network Health" v="92%" tone="info" delta="+4% from last month" />
        <BigStat l="Risk Reduction" v="36%" tone="warning" delta="+8% from last month" />
        <BigStat l="Lives Protected" v="124" tone="purple" delta="This Month" />
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-[1.6fr_1fr] gap-4">
        <Panel title="CCRS Trend" subtitle="30 days">
          <div className="h-72">
            <ResponsiveContainer>
              <LineChart data={trend30}>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="d" stroke="#475569" fontSize={10} />
                <YAxis stroke="#475569" fontSize={10} />
                <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)" }} />
                <Line type="monotone" dataKey="score" stroke="#8B5CF6" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Risk Distribution">
          <div className="h-72">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={dist} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} stroke="none">
                  {dist.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <Panel title="Top Risk Corridors">
          <ul className="text-[12px] space-y-2">
            {["South Central — Vijayawada Sec","Northern — Lucknow Div","Eastern — Howrah Loop","Central — Itarsi Jn","Western — Surat Belt"].map((s,i) => (
              <li key={s} className="flex items-center justify-between border-b border-border/60 last:border-0 pb-2">
                <span className="flex items-center gap-2"><span className="text-mono text-muted-foreground">#{i+1}</span> {s}</span>
                <span className="text-mono text-critical">{92-i*6}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="KPI Summary">
          <ul className="text-[12px] space-y-2">
            <Row l="Punctuality" v="91.2%" />
            <Row l="Mean Time to Resolve" v="14 min" />
            <Row l="False Positive Rate" v="3.8%" tone="text-success" />
            <Row l="Operational Uptime" v="99.97%" tone="text-success" />
            <Row l="Active Sensors" v="48,210" />
          </ul>
        </Panel>
        <Panel title="Compliance & Audit">
          <ul className="text-[12px] space-y-2">
            <Row l="ISO 27001" v="Compliant" tone="text-success" />
            <Row l="NIST CSF" v="Compliant" tone="text-success" />
            <Row l="EN 50128 (Rail)" v="Compliant" tone="text-success" />
            <Row l="Audit Cycle" v="Q4 — In Progress" tone="text-warning" />
            <Row l="Next Review" v="15 Jul" />
          </ul>
        </Panel>
      </div>
    </AppShell>
  );
}

function BigStat({ l, v, tone, delta }: { l: string; v: string; tone: "success"|"info"|"warning"|"purple"; delta: string }) {
  const c = { success: "text-success", info: "text-info", warning: "text-warning", purple: "text-purple" }[tone];
  return (
    <Panel>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{l}</div>
      <div className={`text-mono text-4xl font-bold mt-2 ${c}`}>{v}</div>
      <div className="text-[11px] text-success mt-1">{delta}</div>
    </Panel>
  );
}
function Row({ l, v, tone = "text-foreground" }: { l: string; v: string; tone?: string }) {
  return <li className="flex items-center justify-between border-b border-border/60 last:border-0 pb-2"><span className="text-muted-foreground">{l}</span><span className={`text-mono font-semibold ${tone}`}>{v}</span></li>;
}
