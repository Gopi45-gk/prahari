import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, type FormEvent } from "react";
import { motion } from "framer-motion";
import { Lock, User, KeyRound, ShieldCheck, Fingerprint, AlertCircle } from "lucide-react";
const PRAHARI_LOGO = "https://www.image2url.com/r2/default/images/1781416662920-9e1f0a56-acb7-4f13-9b47-0303090b0de5.png";
export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Authority Login — PRAHARI" },
      { name: "description", content: "Secure command authority sign-in for PRAHARI Railway Operations." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [id, setId] = useState("");
  const [pwd, setPwd] = useState("");
  const [role, setRole] = useState("Control Room Operator");
  const [isSignUp, setIsSignUp] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const [successMsg, setSuccessMsg] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setSuccessMsg("");
    
    if (!id || !pwd) {
      setErr("Email and password are required.");
      return;
    }

    setLoading(true);
    
    try {
      const email = id.includes("@") ? id : `${id.toLowerCase()}@prahari.in`;
      const { signInWithEmailAndPassword, createUserWithEmailAndPassword } = await import("firebase/auth");
      const { auth } = await import("../lib/firebase");
      
      if (isSignUp) {
        const userCred = await createUserWithEmailAndPassword(auth, email, pwd);
        const { doc, setDoc } = await import("firebase/firestore");
        const { db } = await import("../lib/firebase");
        await setDoc(doc(db, "authority_users", userCred.user.uid), {
          operatorId: id,
          role: role,
          email: email,
          createdAt: new Date().toISOString()
        });
      } else {
        await signInWithEmailAndPassword(auth, email, pwd);
      }

      try { localStorage.setItem("prahari_auth", "true"); } catch { /* empty */ }
      navigate({ to: "/" });
    } catch (error: any) {
      if (error.code === 'auth/email-already-in-use') {
        setErr("User already exists. Try signing in.");
      } else if (error.code === 'auth/invalid-credential') {
        setErr("Invalid credentials.");
      } else {
        setErr(error.message || "An error occurred");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-background text-foreground">
      {/* Background grid + glow */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />
      <div className="pointer-events-none absolute -top-40 -left-40 h-[520px] w-[520px] rounded-full bg-info/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-[520px] w-[520px] rounded-full bg-purple/20 blur-3xl" />

      <div className="relative z-10 grid min-h-screen grid-cols-1 lg:grid-cols-2">
        {/* Left brand panel */}
        <div className="hidden lg:flex flex-col justify-between p-10 border-r border-border">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center overflow-hidden rounded-lg bg-white p-1">
              <img src={PRAHARI_LOGO} alt="PRAHARI" className="h-full w-full object-contain" />
            </div>
            <div>
              <div className="text-sm font-bold tracking-wide">PRAHARI</div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground">Authority Platform</div>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="space-y-5 max-w-md"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3 py-1 text-[11px] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />
              Secure Command Channel • TLS 1.3 • mTLS
            </div>
            <h1 className="text-4xl font-semibold leading-tight tracking-tight">
              Railway Command<br />& Control Authority
            </h1>
            <p className="text-sm text-muted-foreground">
              Restricted access. This terminal is monitored. All actions are logged and attributed to the operator identity presented at sign-in.
            </p>
            <ul className="space-y-2 text-[12px] text-muted-foreground">
              <Bullet>Tier-4 clearance required for CCRS overrides</Bullet>
              <Bullet>OT/SCADA isolation enforced via zero-trust gateway</Bullet>
              <Bullet>Multi-factor authentication mandatory</Bullet>
            </ul>
          </motion.div>

          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <span>© PRAHARI Authority • Ministry of Railways</span>
            <span className="text-mono">v4.2.1 • SOC-2 / IEC 62443</span>
          </div>
        </div>

        {/* Right form panel */}
        <div className="flex items-center justify-center p-6 sm:p-10">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="w-full max-w-md rounded-2xl border border-border bg-surface/70 backdrop-blur-xl p-7 shadow-2xl shadow-black/40"
          >
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-info">Authority Login</div>
                <h2 className="text-xl font-semibold mt-1">{isSignUp ? "New Operator Registration" : "Operator Sign-In"}</h2>
              </div>
              <div className="grid h-10 w-10 place-items-center rounded-lg border border-info/30 bg-info/10 text-info glow-info">
                <ShieldCheck className="h-5 w-5" />
              </div>
            </div>

            <form onSubmit={onSubmit} className="space-y-4">
              <Field label="Operator ID" icon={<User className="h-4 w-4" />}>
                <input
                  value={id}
                  onChange={(e) => setId(e.target.value)}
                  placeholder="e.g. CMD-IR-00482"
                  className="w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/60"
                  autoComplete="username"
                />
              </Field>

              <Field label="Password" icon={<Lock className="h-4 w-4" />}>
                <input
                  type="password"
                  value={pwd}
                  onChange={(e) => setPwd(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/60"
                  autoComplete="current-password"
                />
              </Field>

              {isSignUp && (
                <Field label="Authority Role" icon={<ShieldCheck className="h-4 w-4" />}>
                  <select 
                    value={role} 
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full bg-transparent text-[13px] outline-none text-foreground cursor-pointer appearance-none"
                  >
                    <option value="Super Admin" className="bg-surface text-foreground">Super Admin</option>
                    <option value="Railway Board" className="bg-surface text-foreground">Railway Board</option>
                    <option value="General Manager" className="bg-surface text-foreground">General Manager</option>
                    <option value="DRM" className="bg-surface text-foreground">DRM</option>
                    <option value="Control Room Operator" className="bg-surface text-foreground">Control Room Operator</option>
                    <option value="Safety Officer" className="bg-surface text-foreground">Safety Officer</option>
                    <option value="Track Engineer" className="bg-surface text-foreground">Track Engineer</option>
                    <option value="Signal Engineer" className="bg-surface text-foreground">Signal Engineer</option>
                    <option value="Cyber Security Analyst" className="bg-surface text-foreground">Cyber Security Analyst</option>
                    <option value="Station Master" className="bg-surface text-foreground">Station Master</option>
                    <option value="RPF Officer" className="bg-surface text-foreground">RPF Officer</option>
                    <option value="Maintenance Manager" className="bg-surface text-foreground">Maintenance Manager</option>
                    <option value="Executive Authority" className="bg-surface text-foreground">Executive Authority</option>
                  </select>
                </Field>
              )}


              {err && (
                <div className="flex items-center gap-2 rounded-md border border-critical/40 bg-critical/10 px-3 py-2 text-[12px] text-critical">
                  <AlertCircle className="h-4 w-4" />
                  {err}
                </div>
              )}

              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <label className="inline-flex items-center gap-2">
                  <input type="checkbox" className="h-3.5 w-3.5 accent-info" />
                  Remember terminal
                </label>
                <button type="button" className="hover:text-foreground">Forgot password?</button>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="group relative w-full overflow-hidden rounded-lg bg-gradient-to-r from-info to-purple px-4 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-info/25 transition-all hover:shadow-info/40 disabled:opacity-70"
              >
                <span className="relative z-10 inline-flex items-center justify-center gap-2">
                  {isSignUp 
                    ? (loading ? "Registering…" : "Register New Authority Account") 
                    : (loading ? "Authenticating…" : "Authenticate & Enter Command Center")}
                  <Fingerprint className="h-4 w-4" />
                </span>
                <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
              </button>

              <div className="flex items-center gap-3 pt-1">
                <div className="h-px flex-1 bg-border" />
                <span className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground">Alternate</span>
                <div className="h-px flex-1 bg-border" />
              </div>

              <button
                type="button"
                onClick={() => { setIsSignUp(!isSignUp); setErr(""); setSuccessMsg(""); }}
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-surface-2 inline-flex items-center justify-center gap-2"
              >
                <User className="h-4 w-4 text-success" />
                {isSignUp ? "Return to Operator Sign-In" : "Create New User Account"}
              </button>
            </form>

            <div className="mt-6 flex items-center justify-between text-[10px] text-muted-foreground border-t border-border pt-3">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />
                Identity Provider Online
              </span>
              <SessionIdDisplay />
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function SessionIdDisplay() {
  const [sessionId, setSessionId] = useState("");
  useEffect(() => {
    setSessionId(Math.random().toString(36).slice(2, 8).toUpperCase());
  }, []);
  if (!sessionId) return <span className="text-mono">SESSION-ID: ______</span>;
  return <span className="text-mono">SESSION-ID: PRH-{sessionId}</span>;
}

function Field({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">{label}</div>
      <div className="flex items-center gap-2 rounded-lg border border-border bg-background/60 px-3 py-2.5 focus-within:border-info/60 focus-within:bg-background transition-colors">
        <span className="text-muted-foreground">{icon}</span>
        {children}
      </div>
    </label>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span className="mt-1.5 h-1 w-1 rounded-full bg-info" />
      <span>{children}</span>
    </li>
  );
}
