import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard, Map, Activity, Users, Radio, HeartPulse, Shield,
  Siren, Bot, LineChart, Wrench, FileBarChart, Settings,
  Bell, Search, ChevronsLeft, CircleUserRound
} from "lucide-react";
import { useState, useEffect, type ReactNode } from "react";
import { motion } from "framer-motion";
const PRAHARI_LOGO = "https://www.image2url.com/r2/default/images/1781416662920-9e1f0a56-acb7-4f13-9b47-0303090b0de5.png";
const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/network-map", label: "Network Map", icon: Map },
  { to: "/ccrs", label: "CCRS Risk Center", icon: Activity },
  { to: "/crew", label: "Crew Intelligence", icon: Users },
  { to: "/signal", label: "Signal Intelligence", icon: Radio },
  { to: "/infrastructure", label: "Infrastructure Health", icon: HeartPulse },
  { to: "/cyber", label: "Cyber Security", icon: Shield },
  { to: "/incidents", label: "Incident Response", icon: Siren },
  { to: "/copilot", label: "AI Copilot", icon: Bot },
  { to: "/predictive", label: "Predictive Analytics", icon: LineChart },
  { to: "/maintenance", label: "Maintenance Center", icon: Wrench },
  { to: "/reports", label: "Reports & Analytics", icon: FileBarChart },
  { to: "/users", label: "User Management", icon: CircleUserRound },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export function AppShell({ title, subtitle, actions, children }: {
  title: string; subtitle?: string; actions?: ReactNode; children: ReactNode;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? "w-[72px]" : "w-[244px]"} sticky top-0 h-screen shrink-0 border-r border-border bg-sidebar transition-all duration-300 flex flex-col`}
      >
        <div className="flex items-center gap-2 px-4 h-16 border-b border-sidebar-border">
          <div className="grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-lg bg-white p-1">
            <img src={PRAHARI_LOGO} alt="PRAHARI" className="h-full w-full object-contain" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-[13px] font-bold tracking-wide">PRAHARI</div>
              <div className="text-[10px] text-muted-foreground tracking-[0.18em] uppercase">Authority</div>
            </div>
          )}
        </div>
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV.map(({ to, label, icon: Icon }) => {
            const active = pathname === to;
            return (
              <Link
                key={to}
                to={to}
                className={`group flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-all ${
                  active
                    ? "bg-sidebar-accent text-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                }`}
              >
                <span className={`relative flex items-center justify-center ${active ? "text-info" : ""}`}>
                  <Icon className="h-[18px] w-[18px] shrink-0" />
                  {active && (
                    <span className="absolute -left-3 h-5 w-0.5 rounded-r bg-info" />
                  )}
                </span>
                {!collapsed && <span className="truncate">{label}</span>}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="m-2 flex items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
        >
          <ChevronsLeft className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`} />
          {!collapsed && "Collapse"}
        </button>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Header */}
        <header className="sticky top-0 z-20 h-16 border-b border-border bg-background/70 backdrop-blur-xl flex items-center px-6 gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-semibold tracking-tight truncate">{title}</h1>
            {subtitle && <p className="text-xs text-muted-foreground truncate">{subtitle}</p>}
          </div>
          <div className="hidden md:flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-muted-foreground w-64">
            <Search className="h-3.5 w-3.5" />
            <span>Search trains, stations, incidents…</span>
            <kbd className="ml-auto text-[10px] px-1.5 py-0.5 rounded border border-border bg-background">⌘K</kbd>
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <LiveClock />
            <button className="relative grid h-9 w-9 place-items-center rounded-md border border-border bg-surface hover:bg-surface-2">
              <Bell className="h-4 w-4" />
              <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-critical pulse-dot" />
            </button>
            <UserProfile />
          </div>
        </header>

        <motion.main
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="flex-1 p-6"
        >
          {children}
        </motion.main>
      </div>
    </div>
  );
}

function LiveClock() {
  const [now] = useTimeTick();
  if (!now) {
    return (
      <div className="hidden lg:flex flex-col items-end text-[11px] font-mono leading-tight px-3 py-1.5 rounded-md border border-border bg-surface opacity-0">
        <span className="text-foreground">00:00:00</span>
        <span className="text-muted-foreground">XXX 00 XXX</span>
      </div>
    );
  }
  return (
    <div className="hidden lg:flex flex-col items-end text-[11px] font-mono leading-tight px-3 py-1.5 rounded-md border border-border bg-surface">
      <span className="text-foreground">{now.toLocaleTimeString("en-IN", { hour12: false })}</span>
      <span className="text-muted-foreground">{now.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" })}</span>
    </div>
  );
}

function useTimeTick(): [Date | null, (d: Date) => void] {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return [now, setNow as (d: Date) => void];
}

function UserProfile() {
  const [user, setUser] = useState<{ operatorId?: string; role?: string } | null>(null);

  useEffect(() => {
    let unsubscribe: any;
    import("../lib/firebase").then(({ auth, db }) => {
      import("firebase/auth").then(({ onAuthStateChanged }) => {
        import("firebase/firestore").then(({ doc, getDoc }) => {
          unsubscribe = onAuthStateChanged(auth, async (u) => {
            if (u) {
              try {
                const snap = await getDoc(doc(db, "authority_users", u.uid));
                if (snap.exists()) {
                  setUser(snap.data() as any);
                } else {
                  setUser({ operatorId: u.email?.split("@")[0].toUpperCase() || "Operator", role: "Authority" });
                }
              } catch (e) {
                // Fallback if firestore rules block read
                setUser({ operatorId: u.email?.split("@")[0].toUpperCase() || "Operator", role: "Authority" });
              }
            } else {
              setUser(null);
            }
          });
        });
      });
    });
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-surface pl-2 pr-3 py-1.5">
      <CircleUserRound className="h-5 w-5 text-info" />
      <div className="text-[11px] leading-tight">
        <div className="font-medium">{user?.operatorId || "Cmdr. A. Rao"}</div>
        <div className="text-muted-foreground">{user?.role || "CONTROL-OPS"}</div>
      </div>
    </div>
  );
}
