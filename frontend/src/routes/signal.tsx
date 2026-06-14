import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, Bar, StatusPill } from "@/components/panels";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

export const Route = createFileRoute("/signal")({
  head: () => ({ meta: [{ title: "Signal Intelligence — PRAHARI" }, { name: "description", content: "Real-time signal monitoring." }] }),
  component: Signal,
});

const sigTrend = Array.from({ length: 30 }, (_, i) => ({ t: i, latency: 200 + Math.round(Math.sin(i / 3) * 80 + Math.random() * 60) }));

function Signal() {
  return (
    <AppShell title="Signal Intelligence Center" subtitle="Real-time Signal Monitoring">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Signal S-142" subtitle="Section: Vijayawada – Gudur">
          <div className="grid grid-cols-2 gap-3 text-[12px]">
            <Tile l="Status" v="RED" tone="text-critical" />
            <Tile l="Aspect" v="Stop" />
            <Tile l="Last Updated" v="11:24:10" />
            <Tile l="Update Delay" v="8 sec" tone="text-warning" />
            <Tile l="Signal Health" v="62%" tone="text-warning" />
            <Tile l="Communication" v="78%" tone="text-warning" />
          </div>
          <div className="mt-4 space-y-3">
            <div>
              <div className="flex justify-between text-[11px] mb-1"><span className="text-muted-foreground">Signal Health</span><span className="text-mono">62%</span></div>
              <Bar value={62} tone="warning" />
            </div>
            <div>
              <div className="flex justify-between text-[11px] mb-1"><span className="text-muted-foreground">Communication Health</span><span className="text-mono">78%</span></div>
              <Bar value={78} tone="info" />
            </div>
          </div>
        </Panel>

        <Panel title="Signal Timeline" subtitle="Last 1 hour">
          <ul className="text-[12px] space-y-2">
            {[
              ["11:24","RED","Critical"],
              ["11:15","RED","Critical"],
              ["11:07","YELLOW","Pending"],
              ["11:02","RED","Critical"],
              ["10:54","YELLOW","Pending"],
              ["10:48","GREEN","Resolved"],
              ["10:41","YELLOW","Pending"],
            ].map(([t, a, s]) => (
              <li key={t} className="flex items-center gap-3 border-b border-border/60 last:border-0 pb-2">
                <span className="text-mono text-muted-foreground w-14">{t}</span>
                <span className={`text-mono text-[11px] font-semibold ${a==="RED"?"text-critical":a==="YELLOW"?"text-warning":"text-success"}`}>● {a}</span>
                <span className="flex-1" />
                <StatusPill status={s} />
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Signal Latency Trend" subtitle="Communication delay (ms) — last 30 min" className="mt-4">
        <div className="h-56">
          <ResponsiveContainer>
            <LineChart data={sigTrend}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="t" stroke="#475569" fontSize={10} />
              <YAxis stroke="#475569" fontSize={10} />
              <Tooltip contentStyle={{ background: "#0D1525", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8 }} />
              <Line type="monotone" dataKey="latency" stroke="#FFB020" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel title="Associated Trains" subtitle="Currently affected by S-142" className="mt-4"
        action={<button className="text-[11px] text-info hover:underline">View All</button>}>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr className="text-left">
                <th className="py-2 px-3">Train No.</th><th className="py-2 px-3">Train Name</th>
                <th className="py-2 px-3">ETA</th><th className="py-2 px-3">Status</th>
                <th className="py-2 px-3 text-right">Risk</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["12627","Chennai SF Express","11:35","Delayed","High"],
                ["12618","Mallikarjun Express","11:42","Delayed","Medium"],
                ["12686","KSR Bengaluru Exp","11:48","On Time","Low"],
                ["18621","Patliputra Express","12:05","On Time","Low"],
              ].map((r) => (
                <tr key={r[0]} className="border-t border-border/60">
                  <td className="py-2.5 px-3 text-mono">{r[0]}</td>
                  <td className="py-2.5 px-3">{r[1]}</td>
                  <td className="py-2.5 px-3 text-mono text-muted-foreground">{r[2]}</td>
                  <td className="py-2.5 px-3"><StatusPill status={r[3]} /></td>
                  <td className="py-2.5 px-3 text-right"><StatusPill status={r[4]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </AppShell>
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
