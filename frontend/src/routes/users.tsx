import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, StatusPill } from "@/components/panels";
import { Users, UserPlus, Fingerprint, ShieldCheck } from "lucide-react";
import { useState, useEffect } from "react";
import { collection, onSnapshot } from "firebase/firestore";
import { db } from "../lib/firebase";

export const Route = createFileRoute("/users")({
  head: () => ({ meta: [{ title: "User Management — PRAHARI" }, { name: "description", content: "Manage command authority access." }] }),
  component: UsersManagement,
});

function UsersManagement() {
  const [users, setUsers] = useState<any[]>([]);
  
  useEffect(() => {
    const unsub = onSnapshot(collection(db, "authority_users"), (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setUsers(data);
    });
    return () => unsub();
  }, []);

  return (
    <AppShell title="Authority User Management" subtitle="Manage operator identities, clearances, and platform access">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          ["Total Operators", users.length.toString(), "info"],
          ["Active Sessions", "1", "success"],
          ["Super Admins", users.filter(u => u.authority_type === "Super Admin").length.toString(), "purple"],
          ["Pending Audits", "0", "warning"],
        ].map(([l, v, t]) => (
          <Panel key={l}>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{l}</div>
            <div className={`text-mono text-2xl font-bold ${t==="purple"?"text-purple":t==="warning"?"text-warning":t==="success"?"text-success":"text-info"}`}>{v}</div>
          </Panel>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <Panel title="Authority Directory" subtitle="All provisioned accounts">
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  <tr className="text-left">
                    <th className="py-2 px-3">Operator ID</th>
                    <th className="py-2 px-3">Full Name</th>
                    <th className="py-2 px-3">Clearance / Role</th>
                    <th className="py-2 px-3">Zone</th>
                    <th className="py-2 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((r) => (
                    <tr key={r.employee_id} className="border-t border-border/60 hover:bg-surface/40">
                      <td className="py-2.5 px-3 text-mono">{r.employee_id}</td>
                      <td className="py-2.5 px-3 font-semibold">{r.full_name}</td>
                      <td className="py-2.5 px-3 text-muted-foreground">{r.authority_type}</td>
                      <td className="py-2.5 px-3">{r.zone}</td>
                      <td className="py-2.5 px-3 text-right"><StatusPill status="Active" /></td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground">Loading identity matrix...</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Identity Operations">
            <div className="space-y-3">
              <button className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-surface-2 flex items-center justify-between">
                <span className="flex items-center gap-2"><UserPlus className="h-4 w-4 text-info" /> Provision New Account</span>
              </button>
              <button className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-surface-2 flex items-center justify-between">
                <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-success" /> Review Audit Logs</span>
              </button>
              <button className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-surface-2 flex items-center justify-between">
                <span className="flex items-center gap-2"><Fingerprint className="h-4 w-4 text-purple" /> Force OTP Reset</span>
              </button>
            </div>
          </Panel>

          <Panel title="Security Notice">
            <p className="text-[12px] text-muted-foreground leading-relaxed">
              PRAHARI operates on a single-tier access model. Every user provisioned here receives <strong>full access</strong> to the entire platform. Do not provision accounts for unauthorized personnel. All identity changes are securely logged.
            </p>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
