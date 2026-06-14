import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

export function Panel({
  title, subtitle, action, children, className = "", padded = true,
}: {
  title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string; padded?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`glass rounded-xl ${className}`}
    >
      {(title || action) && (
        <div className="flex items-start justify-between px-5 pt-4 pb-3">
          <div className="min-w-0">
            {title && <div className="text-[13px] font-semibold tracking-tight">{title}</div>}
            {subtitle && <div className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</div>}
          </div>
          {action}
        </div>
      )}
      <div className={padded ? "px-5 pb-5" : ""}>{children}</div>
    </motion.div>
  );
}

export function KpiCard({
  label, value, delta, tone = "info", icon, footer,
}: {
  label: string; value: string | number; delta?: { value: string; up?: boolean };
  tone?: "info" | "critical" | "warning" | "success" | "purple"; icon?: ReactNode; footer?: string;
}) {
  const toneMap: Record<string, string> = {
    info: "text-info from-info/20 to-info/0",
    critical: "text-critical from-critical/20 to-critical/0",
    warning: "text-warning from-warning/20 to-warning/0",
    success: "text-success from-success/10 to-success/0",
    purple: "text-purple from-purple/20 to-purple/0",
  };
  return (
    <Panel padded={false} className="overflow-hidden relative">
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${toneMap[tone]}`} />
      <div className="p-5">
        <div className="flex items-center justify-between">
          <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
          {icon && <div className={`${toneMap[tone].split(" ")[0]} opacity-80`}>{icon}</div>}
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <div className={`text-mono text-3xl font-bold ${toneMap[tone].split(" ")[0]}`}>{value}</div>
          {delta && (
            <span className={`inline-flex items-center gap-0.5 text-[11px] ${delta.up ? "text-success" : "text-critical"}`}>
              {delta.up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {delta.value}
            </span>
          )}
        </div>
        {footer && <div className="mt-1 text-[11px] text-muted-foreground">{footer}</div>}
      </div>
    </Panel>
  );
}

export function StatusPill({ status }: { status: "Active" | "Resolved" | "Pending" | "Critical" | "High" | "Medium" | "Low" | "Delayed" | "On Time" | "Stopped" | string }) {
  const map: Record<string, string> = {
    Active: "bg-info/15 text-info border-info/30",
    Resolved: "bg-success/15 text-success border-success/30",
    Pending: "bg-warning/15 text-warning border-warning/30",
    Critical: "bg-critical/15 text-critical border-critical/30",
    High: "bg-critical/15 text-critical border-critical/30",
    Medium: "bg-warning/15 text-warning border-warning/30",
    Low: "bg-success/15 text-success border-success/30",
    Delayed: "bg-critical/15 text-critical border-critical/30",
    Stopped: "bg-warning/15 text-warning border-warning/30",
    "On Time": "bg-success/15 text-success border-success/30",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${map[status] ?? "bg-surface text-muted-foreground border-border"}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current pulse-dot" />
      {status}
    </span>
  );
}

export function Gauge({ value, max = 100, label, tone = "critical", size = 200 }: {
  value: number; max?: number; label?: string; tone?: "critical" | "warning" | "success" | "info"; size?: number;
}) {
  const radius = size / 2 - 14;
  const circumference = 2 * Math.PI * radius;
  const safeValue = isNaN(value) ? 0 : value;
  const pct = Math.min(1, safeValue / max);
  const offset = circumference * (1 - pct);
  const colorMap = { critical: "#FF4D4F", warning: "#FFB020", success: "#22C55E", info: "#3B82F6" };
  const stroke = colorMap[tone];
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={`g-${tone}`} x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="1" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0.4" />
          </linearGradient>
        </defs>
        <circle cx={size/2} cy={size/2} r={radius} stroke="rgba(255,255,255,0.06)" strokeWidth={10} fill="none" />
        <motion.circle
          cx={size/2} cy={size/2} r={radius}
          stroke={`url(#g-${tone})`} strokeWidth={10} strokeLinecap="round" fill="none"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 8px ${stroke}80)` }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="text-mono text-4xl font-bold" style={{ color: stroke }}>{safeValue}</div>
          <div className="text-[10px] text-muted-foreground">/{max}</div>
          {label && <div className="mt-1 text-[10px] font-semibold tracking-[0.18em] uppercase" style={{ color: stroke }}>{label}</div>}
        </div>
      </div>
    </div>
  );
}

export function Bar({ value, max = 100, tone = "info" }: { value: number; max?: number; tone?: "info"|"critical"|"warning"|"success"|"purple" }) {
  const map = { info: "bg-info", critical: "bg-critical", warning: "bg-warning", success: "bg-success", purple: "bg-purple" };
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
      <motion.div
        initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.9, ease: "easeOut" }}
        className={`h-full rounded-full ${map[tone]}`}
        style={{ boxShadow: `0 0 12px currentColor` }}
      />
    </div>
  );
}
