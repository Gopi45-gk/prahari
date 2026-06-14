import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panels";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — PRAHARI" }, { name: "description", content: "Platform configuration and preferences." }] }),
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <AppShell title="Settings" subtitle="Platform Configuration">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel title="Operator Profile">
          <ul className="text-[12px] space-y-2">
            <Row l="Name" v="Cmdr. Anirudh Rao" />
            <Row l="Role" v="Control-Ops Lead" />
            <Row l="Zone" v="Central Command" />
            <Row l="Shift" v="A — 06:00 to 14:00" />
            <Row l="Clearance" v="Tier-4 (SECRET)" tone="text-purple" />
          </ul>
        </Panel>
        <Panel title="Notifications">
          {["Critical Alerts","Crew Fatigue Events","Cyber Threats","Maintenance Due","Daily Briefing"].map((s, i) => (
            <div key={s} className="flex items-center justify-between border-b border-border/60 last:border-0 py-2 text-[12px]">
              <span>{s}</span>
              <Toggle on={i !== 4} />
            </div>
          ))}
        </Panel>
        <Panel title="System Preferences">
          <ul className="text-[12px] space-y-2">
            <Row l="Theme" v="Ultra Dark Pro" />
            <Row l="Language" v="English (IN)" />
            <Row l="Time Format" v="24-hour IST" />
            <Row l="Map Provider" v="PRAHARI Digital Twin" />
            <Row l="API Version" v="v4.2.1" tone="text-info" />
          </ul>
        </Panel>
      </div>

      <Panel title="Integrations" className="mt-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[12px]">
          {[
            ["SCADA Bridge","Connected","success"],
            ["Crew DB","Connected","success"],
            ["Weather API","Connected","success"],
            ["Predictive ML","Connected","success"],
            ["IoT Sensors","Degraded","warning"],
            ["RailNet OT","Connected","success"],
            ["SOC Feed","Connected","success"],
            ["Audit Trail","Connected","success"],
          ].map(([l, s, t]) => (
            <div key={l} className="rounded-md border border-border/60 bg-surface/60 px-3 py-3">
              <div className="flex items-center justify-between">
                <span>{l}</span>
                <span className={`h-2 w-2 rounded-full ${t==="success"?"bg-success":"bg-warning"} pulse-dot`} />
              </div>
              <div className={`text-[10px] mt-1 ${t==="success"?"text-success":"text-warning"}`}>{s}</div>
            </div>
          ))}
        </div>
      </Panel>
    </AppShell>
  );
}
function Row({ l, v, tone = "text-foreground" }: { l: string; v: string; tone?: string }) {
  return <li className="flex items-center justify-between border-b border-border/60 last:border-0 pb-2"><span className="text-muted-foreground">{l}</span><span className={`text-mono font-semibold ${tone}`}>{v}</span></li>;
}
function Toggle({ on }: { on: boolean }) {
  return (
    <span className={`relative inline-block h-5 w-9 rounded-full ${on ? "bg-info" : "bg-white/10"}`}>
      <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${on ? "left-4" : "left-0.5"}`} />
    </span>
  );
}
