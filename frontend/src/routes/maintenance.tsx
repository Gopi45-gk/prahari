import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, Bar, StatusPill } from "@/components/panels";

export const Route = createFileRoute("/maintenance")({
  head: () => ({ meta: [{ title: "Maintenance Intelligence — PRAHARI" }, { name: "description", content: "AI-powered maintenance prioritization." }] }),
  component: Maintenance,
});

const ASSETS = [
  ["TRK-142","Track","KM 142/7","92","Critical"],
  ["BRG-098","Bridge","NH 98/3","85","High"],
  ["SIG-142","Signal","S-142","80","High"],
  ["TRK-254","Track","KM 254/1","76","High"],
  ["PTR-365","Point Machine","PM-365","72","Medium"],
  ["OHE-091","Overhead Eq.","SEC-091","68","Medium"],
  ["SIG-208","Signal","S-208","61","Medium"],
  ["BRG-118","Bridge","NH 118/2","54","Low"],
];

function Maintenance() {
  return (
    <AppShell title="Maintenance Intelligence" subtitle="AI-Powered Maintenance Prioritization">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          ["Assets Monitored","12,458","text-info"],
          ["High Priority","142","text-critical"],
          ["Due Maintenance","326","text-warning"],
        ].map(([l, v, c]) => (
          <Panel key={l}>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{l}</div>
            <div className={`text-mono text-3xl font-bold ${c}`}>{v}</div>
          </Panel>
        ))}
      </div>

      <Panel title="Top Priority Assets" subtitle="Ranked by AI failure probability" className="mt-4"
        action={<button className="text-[11px] text-info hover:underline">View All Assets</button>}>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr className="text-left">
                <th className="py-2 px-3">Asset ID</th><th className="py-2 px-3">Asset Type</th>
                <th className="py-2 px-3">Location</th><th className="py-2 px-3">Failure Probability</th>
                <th className="py-2 px-3">Priority</th>
              </tr>
            </thead>
            <tbody>
              {ASSETS.map((r) => {
                const prob = parseInt(r[3]);
                const tone = prob >= 85 ? "critical" : prob >= 70 ? "warning" : "info";
                return (
                  <tr key={r[0]} className="border-t border-border/60 hover:bg-surface/40">
                    <td className="py-2.5 px-3 text-mono">{r[0]}</td>
                    <td className="py-2.5 px-3">{r[1]}</td>
                    <td className="py-2.5 px-3 text-muted-foreground">{r[2]}</td>
                    <td className="py-2.5 px-3 w-[280px]">
                      <div className="flex items-center gap-3">
                        <div className="flex-1"><Bar value={prob} tone={tone as never} /></div>
                        <span className="text-mono w-10 text-right">{prob}%</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3"><StatusPill status={r[4]} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Maintenance Recommendations" className="mt-4">
        <ul className="space-y-2 text-[12px]">
          {[
            "Schedule track grinding on KM 142/0 — KM 143/0 within 48h",
            "Replace signal relay on S-142 (predicted failure in 6 days)",
            "Inspect Bridge BRG-098 — vibration trending upward",
            "Preventive overhaul of point machine PM-365",
          ].map((t, i) => (
            <li key={i} className="rounded-md border border-border/60 bg-surface/60 px-3 py-2.5 flex items-start gap-2">
              <span className="text-info">→</span><span>{t}</span>
            </li>
          ))}
        </ul>
      </Panel>
    </AppShell>
  );
}
