import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, StatusPill } from "@/components/panels";
import { LiveRailwayMap as IndiaMap } from "@/components/live-railway-map";
import { useState, useEffect, useRef } from "react";
import { API_BASE } from "@/hooks/use-prahari-api";

export const Route = createFileRoute("/network-map")({
  head: () => ({ meta: [{ title: "National Railway Digital Twin — PRAHARI" }, { name: "description", content: "Live national railway network digital twin." }] }),
  component: NetworkMap,
});

type TrainSummary = { train_id: string; ccrs: number; risk_level: string; route: string };

type LiveUpdate = { time: string; t: string; tone: string };

function NetworkMap() {
  const [layers, setLayers] = useState({
    trains: true, signals: true, stations: true, risk: true, incidents: true, weather: false, tracks: true,
  });
  const toggle = (k: keyof typeof layers) => setLayers((p) => ({ ...p, [k]: !p[k] }));

  const [activeTrains, setActiveTrains] = useState(0);
  const [runningTrains, setRunningTrains] = useState(0);
  const [delayedTrains, setDelayedTrains] = useState(0);
  const [stoppedTrains, setStoppedTrains] = useState(0);

  const [updates, setUpdates] = useState<LiveUpdate[]>([]);
  const updatesRef = useRef<LiveUpdate[]>([]);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/dashboard-summary`);
        if (!res.ok || cancelled) return;
        const data = await res.json();

        const trains: TrainSummary[] = data.trains ?? [];
        const total = trains.length;
        const critical = trains.filter((t: TrainSummary) => t.risk_level === "Critical").length;
        const high = trains.filter((t: TrainSummary) => t.risk_level === "High").length;
        const safe = total - critical - high;

        setActiveTrains(total);
        setRunningTrains(safe);
        setDelayedTrains(high);
        setStoppedTrains(critical);

        // Build live updates from train data
        const now = new Date();
        const ts = now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });

        const newUpdates: LiveUpdate[] = [];
        for (const train of trains) {
          if (train.risk_level === "Critical") {
            newUpdates.push({
              time: ts,
              t: `Train ${train.train_id} — CRITICAL (CCRS ${train.ccrs})`,
              tone: "Critical",
            });
          } else if (train.risk_level === "High") {
            newUpdates.push({
              time: ts,
              t: `Train ${train.train_id} — HIGH RISK (CCRS ${train.ccrs})`,
              tone: "Pending",
            });
          }
        }

        if (newUpdates.length === 0) {
          newUpdates.push({
            time: ts,
            t: `All ${total} trains operating safely`,
            tone: "Active",
          });
        }

        const merged = [...newUpdates, ...updatesRef.current].slice(0, 5);
        updatesRef.current = merged;
        setUpdates(merged);
      } catch { /* ignore */ }
    };

    fetchData();
    const id = setInterval(fetchData, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <AppShell title="National Railway Digital Twin" subtitle="Live Railway Network — All Zones / All Divisions">
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4">
        <Panel title="Network Map" subtitle="Real-time Digital Twin"
          action={
            <div className="flex gap-2 text-[11px]">
              <select className="rounded-md bg-surface border border-border px-2 py-1"><option>All Zones</option></select>
              <select className="rounded-md bg-surface border border-border px-2 py-1"><option>All Divisions</option></select>
              <select className="rounded-md bg-surface border border-border px-2 py-1"><option>All Trains</option></select>
            </div>
          }>
          <IndiaMap height={580} showLayers={layers} />
        </Panel>

        <div className="space-y-4">
          <Panel title="Map Layers">
            <ul className="text-[12px] space-y-2">
              {([
                ["trains","Train Positions"],
                ["signals","Signals"],
                ["stations","Stations"],
                ["risk","Risk Zones"],
                ["incidents","Incidents"],
                ["weather","Weather"],
                ["tracks","Track Health"],
              ] as const).map(([k,l]) => (
                <li key={k} className="flex items-center justify-between">
                  <span>{l}</span>
                  <button onClick={() => toggle(k)} className={`relative h-5 w-9 rounded-full transition ${layers[k] ? "bg-info" : "bg-white/10"}`}>
                    <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${layers[k] ? "left-4" : "left-0.5"}`} />
                  </button>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Trains in View">
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              {[
                ["Total", String(activeTrains), "text-foreground"],
                ["Running", String(runningTrains), "text-success"],
                ["Delayed", String(delayedTrains), "text-warning"],
                ["Stopped", String(stoppedTrains), "text-critical"],
              ].map(([l,v,c]) => (
                <div key={l} className="rounded-md border border-border/60 bg-surface/60 px-3 py-2">
                  <div className="text-[10px] uppercase text-muted-foreground tracking-wider">{l}</div>
                  <div className={`text-mono text-xl font-bold ${c}`}>{v}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Live Updates">
            <ul className="space-y-2 max-h-72 overflow-y-auto text-[12px]">
              {updates.map((u, i) => (
                <li key={i} className="flex items-start gap-2 border-b border-border/60 last:border-0 pb-2 last:pb-0">
                  <span className="text-mono text-[10px] text-muted-foreground w-10 mt-0.5">{u.time}</span>
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{u.t}</div>
                  </div>
                  <StatusPill status={u.tone} />
                </li>
              ))}
              {updates.length === 0 && (
                <li className="text-center text-muted-foreground py-4">Waiting for data...</li>
              )}
            </ul>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
