import { createFileRoute } from "@tanstack/react-router";
import { db } from "../lib/firebase";
import { collection, addDoc, setDoc, doc } from "firebase/firestore";
import { useState } from "react";

export const Route = createFileRoute("/seed")({
  component: SeedPage,
});

const HAZARDS = [
  { reportId: "INC-2025-1427", hazardType: "Track Obstruction", location: "KM 142/7", severity: "Critical", status: "Active", createdAt: "11:22 AM" },
  { reportId: "INC-2025-1426", hazardType: "Signal Failure", location: "S-142", severity: "High", status: "Active", createdAt: "11:15 AM" },
  { reportId: "INC-2025-1425", hazardType: "Crew Fatigue", location: "Train 12627", severity: "Critical", status: "Active", createdAt: "11:10 AM" },
  { reportId: "INC-2025-1424", hazardType: "Animal on Track", location: "KM 98/2", severity: "Medium", status: "Pending", createdAt: "10:48 AM" },
  { reportId: "INC-2025-1423", hazardType: "Coach Damage", location: "Train 12618", severity: "Low", status: "Resolved", createdAt: "09:30 AM" },
  { reportId: "INC-2025-1422", hazardType: "Cyber Anomaly", location: "RTU-118", severity: "High", status: "Pending", createdAt: "09:12 AM" },
  { reportId: "INC-2025-1421", hazardType: "Bridge Vibration", location: "Br-082", severity: "Medium", status: "Active", createdAt: "08:55 AM" },
  { reportId: "INC-2025-1420", hazardType: "Power Loss", location: "Sec S-118", severity: "High", status: "Resolved", createdAt: "08:30 AM" },
];

const CREWS = [
  { crewId: "LP-98214", name: "Rajesh Kumar", train: "12627 (SBC-NDLS)", status: "Active", riskLevel: "Critical" },
  { crewId: "LP-83712", name: "Suresh Menon", train: "12007 (MAS-MYS)", status: "Active", riskLevel: "Normal" },
  { crewId: "ALP-91823", name: "Amit Singh", train: "12627 (SBC-NDLS)", status: "Active", riskLevel: "Warning" },
  { crewId: "LP-74621", name: "Prakash V", train: "16526 (SBC-CAPE)", status: "Off-Duty", riskLevel: "Normal" },
];

const TRACKS = [
  { trackId: "SEC-142/7", healthScore: 42, status: "Critical", nextInspection: "Immediate" },
  { trackId: "SEC-098/2", healthScore: 88, status: "Normal", nextInspection: "14 Jun 2026" },
  { trackId: "SEC-118/5", healthScore: 65, status: "Warning", nextInspection: "12 Jun 2026" },
];

const CYBERS = [
  { alertId: "CYB-7721", threatType: "DDoS Attempt", target: "Signal Gateway S-142", severity: "High", status: "Mitigated", time: "11:15 AM" },
  { alertId: "CYB-7720", threatType: "Unauthorized Access", target: "RTU-118", severity: "Critical", status: "Active", time: "09:12 AM" },
  { alertId: "CYB-7719", threatType: "Malware Signature", target: "Crew Tablet T-42", severity: "Medium", status: "Isolated", time: "08:50 AM" },
  { alertId: "CYB-7718", threatType: "Port Scan", target: "Zone Firewall", severity: "Low", status: "Logged", time: "07:30 AM" },
];

const CCRS_SCORES = [
  { trainId: "12627", crewRisk: 88, trackRisk: 42, cyberRisk: 10, operationalRisk: 30, ccrs: 88, riskLevel: "Critical" },
  { trainId: "12007", crewRisk: 12, trackRisk: 15, cyberRisk: 5, operationalRisk: 10, ccrs: 15, riskLevel: "Normal" },
  { trainId: "16526", crewRisk: 45, trackRisk: 20, cyberRisk: 0, operationalRisk: 25, ccrs: 45, riskLevel: "Warning" },
];

function SeedPage() {
  const [log, setLog] = useState("");

  const seedDB = async () => {
    try {
      setLog("Seeding Started...\n");
      
      for (const hazard of HAZARDS) {
        await addDoc(collection(db, "hazard_reports"), hazard);
      }
      setLog(l => l + "Seeded hazard_reports\n");

      for (const crew of CREWS) {
        await addDoc(collection(db, "crew_alertness"), crew);
      }
      setLog(l => l + "Seeded crew_alertness\n");

      // Register Super Admin in Firebase Auth
      const { createUserWithEmailAndPassword, getAuth } = await import("firebase/auth");
      const auth = getAuth();
      try {
        await createUserWithEmailAndPassword(auth, "cmd-ir-00482@prahari.in", "password123");
        setLog(l => l + "Created Super Admin in Firebase Auth: cmd-ir-00482@prahari.in\n");
      } catch (err: any) {
        if (err.code === "auth/email-already-in-use") {
          setLog(l => l + "Super Admin already exists in Firebase Auth.\n");
        } else {
          setLog(l => l + "Failed to create Super Admin: " + err.message + "\n");
        }
      }

      for (const track of TRACKS) {
        await addDoc(collection(db, "track_health"), track);
      }
      setLog(l => l + "Seeded track_health\n");

      for (const cyber of CYBERS) {
        await addDoc(collection(db, "cyber_alerts"), cyber);
      }
      setLog(l => l + "Seeded cyber_alerts\n");

      for (const score of CCRS_SCORES) {
        await addDoc(collection(db, "ccrs_scores"), score);
      }
      setLog(l => l + "Seeded ccrs_scores\n");

      setLog(l => l + "All Mock Data Successfully Pushed to Firestore!\n");
    } catch (e: any) {
      setLog(l => l + "Error: " + e.message + "\n");
    }
  };

  return (
    <div style={{ padding: "50px", color: "white" }}>
      <h1>Firestore Seeder</h1>
      <button onClick={seedDB} style={{ padding: "10px", background: "#fff", color: "black", cursor: "pointer" }}>Start Seeding</button>
      <pre style={{ marginTop: "20px" }}>{log}</pre>
    </div>
  );
}
