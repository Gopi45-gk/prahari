import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { motion } from "framer-motion";
const PRAHARI_LOGO = "https://www.image2url.com/r2/default/images/1781416662920-9e1f0a56-acb7-4f13-9b47-0303090b0de5.png";
export const Route = createFileRoute("/splash")({
  head: () => ({ meta: [{ title: "PRAHARI — Initializing" }] }),
  component: Splash,
});

function Splash() {
  const navigate = useNavigate();
  useEffect(() => {
    const t = setTimeout(() => {
      try { sessionStorage.setItem("prahari_splash_shown", "1"); } catch { /* empty */ }
      try { localStorage.removeItem("prahari_auth"); } catch { /* empty */ } // Force login
      navigate({ to: "/login" });
    }, 2400);
    return () => clearTimeout(t);
  }, [navigate]);


  return (
    <div className="fixed inset-0 z-[9999] grid place-items-center bg-white">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
        className="flex flex-col items-center gap-6"
      >
        <motion.img
          src={PRAHARI_LOGO}
          alt="PRAHARI Authority"
          className="h-48 w-auto object-contain"
          initial={{ y: 8 }}
          animate={{ y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          className="h-0.5 w-40 overflow-hidden rounded-full bg-black/10"
        >
          <motion.div
            className="h-full w-1/3 bg-gradient-to-r from-transparent via-black/60 to-transparent"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          />
        </motion.div>
      </motion.div>
    </div>
  );
}
