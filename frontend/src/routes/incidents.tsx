import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, StatusPill } from "@/components/panels";
import { AlertOctagon, Search, ClipboardCheck, CheckCircle2 } from "lucide-react";
import { useState, useEffect } from "react";
import { collection, onSnapshot } from "firebase/firestore";
import { db } from "../lib/firebase";

export const Route = createFileRoute("/incidents")({
  head: () => ({ meta: [{ title: "Incident Response — PRAHARI" }, { name: "description", content: "Manage and resolve railway incidents." }] }),
  component: Incidents,
});

function Incidents() {
  const [incidents, setIncidents] = useState<any[]>([]);

  useEffect(() => {
    const unsubHazards = onSnapshot(collection(db, "hazard_reports"), (snapshot) => {
      const hazards = snapshot.docs.map(doc => {
        const data = doc.data();
        return [data.reportId || doc.id, data.hazardType, data.location, data.severity || "Medium", data.status || "Pending", data.createdAt || "Just Now"];
      });
      setIncidents(prev => {
        const filtered = prev.filter(i => !i[0].startsWith("INC-")); // primitive merge logic for simplicity
        return [...filtered, ...hazards];
      });
    });

    const unsubSOS = onSnapshot(collection(db, "sos_alerts"), (snapshot) => {
      const sos = snapshot.docs.map(doc => {
        const data = doc.data();
        return [data.incidentId || doc.id, `SOS: ${data.incidentType}`, data.location, data.severity || "Critical", data.status || "Active", data.createdAt || "Just Now"];
      });
      setIncidents(prev => {
        const filtered = prev.filter(i => i[0].startsWith("INC-"));
        return [...filtered, ...sos];
      });
    });

    return () => {
      unsubHazards();
      unsubSOS();
    };
  }, []);

  return (
    <AppShell title="Incident Response Center" subtitle="Manage & Resolve Incidents">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          ["All Incidents", "7", "info"],
          ["Active", "4", "critical"],
          ["Pending", "2", "warning"],
          ["Resolved", "1", "success"],
        ].map(([l, v, t]) => (
          <Panel key={l}>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{l}</div>
            <div className={`text-mono text-2xl font-bold ${t==="critical"?"text-critical":t==="warning"?"text-warning":t==="success"?"text-success":"text-info"}`}>{v}</div>
          </Panel>
        ))}
      </div>

      <Panel title="Active Incidents" subtitle="Latest reports">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr className="text-left">
                <th className="py-2 px-3">Incident ID</th><th className="py-2 px-3">Type</th>
                <th className="py-2 px-3">Location</th><th className="py-2 px-3">Severity</th>
                <th className="py-2 px-3">Status</th><th className="py-2 px-3 text-right">Reported At</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((r) => (
                <tr key={r[0]} className="border-t border-border/60 hover:bg-surface/40">
                  <td className="py-2.5 px-3 text-mono">{r[0]}</td>
                  <td className="py-2.5 px-3">{r[1]}</td>
                  <td className="py-2.5 px-3 text-muted-foreground">{r[2]}</td>
                  <td className="py-2.5 px-3"><StatusPill status={r[3]} /></td>
                  <td className="py-2.5 px-3"><StatusPill status={r[4]} /></td>
                  <td className="py-2.5 px-3 text-right text-mono text-muted-foreground">{r[5]}</td>
                </tr>
              ))}
              {incidents.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">Waiting for live reports from field units...</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Incident Workflow" subtitle="Standard response pipeline" className="mt-4">
        <div className="flex items-center justify-between gap-3 overflow-x-auto py-3">
          {[
            { l: "Detected", Icon: AlertOctagon, tone: "critical", active: true },
            { l: "Assessing", Icon: Search, tone: "warning", active: true },
            { l: "Action Taken", Icon: ClipboardCheck, tone: "info", active: true },
            { l: "Resolved", Icon: CheckCircle2, tone: "success", active: false },
          ].map((s, i, arr) => (
            <div key={s.l} className="flex items-center gap-3 flex-1 min-w-[140px]">
              <div className="flex flex-col items-center text-center">
                <div className={`grid h-14 w-14 place-items-center rounded-2xl border bg-surface ${
                  s.tone==="critical"?"border-critical/30 text-critical glow-critical":
                  s.tone==="warning"?"border-warning/30 text-warning glow-warning":
                  s.tone==="info"?"border-info/30 text-info glow-info":
                  "border-success/30 text-success glow-success"
                }`}>
                  <s.Icon className="h-6 w-6" />
                </div>
                <div className="mt-2 text-[11px]">{s.l}</div>
              </div>
              {i < arr.length - 1 && <div className="flex-1 h-px bg-gradient-to-r from-info/40 to-info/0 dash-flow" />}
            </div>
          ))}
        </div>
      </Panel>
    </AppShell>
  );
}
