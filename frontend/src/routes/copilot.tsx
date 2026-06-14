import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panels";
import { Bot, Send, Sparkles, User } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/copilot")({
  head: () => ({ meta: [{ title: "PRAHARI AI Copilot" }, { name: "description", content: "Natural language railway safety assistant." }] }),
  component: Copilot,
});

const SUGGESTIONS = [
  "Why is Train 12627 marked as critical?",
  "Show all high-risk trains in Eastern Zone",
  "Explain CCRS spike near KM 142/7",
  "Top 3 mitigation actions for current incidents",
];

function Copilot() {
  const [messages, setMessages] = useState([
    { role: "ai" as const, text: "Welcome, Commander. I'm PRAHARI AI — your railway safety assistant. Ask about any train, signal, crew or incident." },
    { role: "user" as const, text: "Why is Train 12627 marked as critical?" },
    { role: "ai" as const, text: "Train 12627 — Chennai SF Express", structured: true },
  ]);
  const [input, setInput] = useState("");
  return (
    <AppShell title="PRAHARI AI Copilot" subtitle="Your AI Assistant for Railway Safety">
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-4">
        <Panel padded={false} className="flex flex-col h-[calc(100vh-200px)]">
          <div className="flex items-center gap-2 px-5 py-3 border-b border-border">
            <div className="grid h-8 w-8 place-items-center rounded-md bg-gradient-to-br from-purple to-info text-white">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <div className="text-[13px] font-semibold">PRAHARI AI</div>
              <div className="text-[10px] text-success flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" /> Online • GPT-Rail v4</div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role==="user" ? "justify-end" : ""}`}>
                {m.role==="ai" && <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-purple/15 text-purple"><Bot className="h-4 w-4" /></div>}
                <div className={`max-w-[80%] rounded-xl px-4 py-3 text-[13px] leading-relaxed ${
                  m.role==="user" ? "bg-info text-white" : "bg-surface border border-border"
                }`}>
                  {m.structured ? <AnalysisCard /> : m.text}
                </div>
                {m.role==="user" && <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-info/20 text-info"><User className="h-4 w-4" /></div>}
              </div>
            ))}
          </div>

          <div className="border-t border-border p-3">
            <div className="flex flex-wrap gap-2 mb-3">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => setInput(s)} className="text-[11px] px-2.5 py-1 rounded-full border border-border bg-surface hover:bg-surface-2 text-muted-foreground hover:text-foreground">
                  {s}
                </button>
              ))}
            </div>
            <form onSubmit={async (e) => { 
              e.preventDefault(); 
              if(!input.trim()) return; 
              
              const newMessages = [...messages, { role: "user" as const, text: input }];
              setMessages([...newMessages, { role: "ai" as const, text: "Analyzing..." }]); 
              setInput(""); 
              
              try {
                const res = await fetch("http://localhost:8001/api/copilot", {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    model: "nvidia/nemotron-3-ultra-550b-a55b",
                    messages: newMessages.filter(m => !m.structured).map(m => ({ 
                      role: m.role === "ai" ? "assistant" : "user", 
                      content: m.text 
                    })),
                    temperature: 1,
                    top_p: 0.95,
                    max_tokens: 16384,
                    chat_template_kwargs: { enable_thinking: true },
                    reasoning_budget: 16384,
                    stream: true
                  })
                });

                if (!res.body) throw new Error("No body");
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let aiText = "";

                while (true) {
                  const { value, done } = await reader.read();
                  if (done) break;
                  
                  const chunkStr = decoder.decode(value, { stream: true });
                  const lines = chunkStr.split("\n").filter(l => l.trim().startsWith("data: "));
                  
                  for (const line of lines) {
                    const data = line.replace(/^data: /, "").trim();
                    if (data === "[DONE]") break;
                    
                    try {
                      const parsed = JSON.parse(data);
                      if (!parsed.choices || parsed.choices.length === 0) continue;
                      
                      const delta = parsed.choices[0].delta;
                      const reasoning = delta.reasoning_content;
                      const content = delta.content;
                      
                      if (reasoning) aiText += reasoning;
                      if (content) aiText += content;
                      
                      setMessages([...newMessages, { role: "ai" as const, text: aiText }]);
                    } catch (err) {
                      // Ignore JSON parse errors for incomplete chunks
                    }
                  }
                }
              } catch (err) {
                console.error("Copilot API Error:", err);
                setMessages([...newMessages, { role: "ai" as const, text: "Connection error. Please try again." }]);
              }
            }}
              className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
              <Sparkles className="h-4 w-4 text-purple" />
              <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask anything about railway operations…" className="flex-1 bg-transparent outline-none text-[13px] placeholder:text-muted-foreground" />
              <button type="submit" className="grid h-7 w-7 place-items-center rounded-md bg-info text-white hover:bg-info/90"><Send className="h-3.5 w-3.5" /></button>
            </form>
          </div>
        </Panel>

        <div className="space-y-4">
          <Panel title="Capabilities">
            <ul className="text-[12px] space-y-2 text-muted-foreground">
              <li>• Natural language queries</li>
              <li>• Incident root-cause explanations</li>
              <li>• Risk mitigation recommendations</li>
              <li>• Predictive scenario analysis</li>
              <li>• Multi-language (EN / HI / FR)</li>
            </ul>
          </Panel>
          <Panel title="Recent Conversations">
            <ul className="text-[12px] space-y-2">
              {["KM 142/7 incident root cause","Crew swap recommendation — LP2001","Eastern Zone risk briefing","Cyber anomaly explanation"].map(s => (
                <li key={s} className="rounded-md border border-border/60 bg-surface/60 px-3 py-2 hover:bg-surface-2 cursor-pointer">{s}</li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}

function AnalysisCard() {
  return (
    <div className="space-y-3">
      <div className="font-semibold">Here is the analysis of Train 12627:</div>
      <ul className="space-y-1.5 text-[12px]">
        <li>• <span className="text-critical">High fatigue</span> detected in Loco Pilot (Alertness: 22)</li>
        <li>• Signal communication delay in section S-142 (8 sec)</li>
        <li>• Track anomaly detected near KM 142/7</li>
        <li>• Combined risk score (CCRS) is <span className="text-critical font-semibold">91 (Critical)</span></li>
      </ul>
      <div>
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1.5">Recommended Actions</div>
        <ul className="space-y-1.5 text-[12px]">
          <li>• Ensure crew alertness (take immediate action)</li>
          <li>• Resolve signal communication delay</li>
          <li>• Reduce speed and increase monitoring</li>
        </ul>
      </div>
    </div>
  );
}
