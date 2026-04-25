"use client";

import { motion } from "framer-motion";
import { X, Cpu, Database, Zap, Brain, MessageSquare, BarChart2 } from "lucide-react";

const AGENTS = [
  {
    icon: Brain,
    label: "Agent 1 — JD Parser",
    desc: "Parses raw Job Description text into structured JSON (skills, seniority, location, budget).",
    color: "bg-violet-500/10 text-violet-500 border-violet-500/20",
  },
  {
    icon: Database,
    label: "Agent 2 — Talent Scout",
    desc: "Runs a semantic vector search over the ChromaDB candidate pool and returns top matches with Match Scores.",
    color: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  },
  {
    icon: MessageSquare,
    label: "Agent 3 — Recruiter AI",
    desc: "Adopts the persona of a senior recruiter and asks targeted technical questions based on the JD.",
    color: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  },
  {
    icon: Cpu,
    label: "Agent 4 — Candidate AI",
    desc: "Adopts the persona of each candidate and answers based on their actual skills, bio, and interest level.",
    color: "bg-cyan-500/10 text-cyan-500 border-cyan-500/20",
  },
  {
    icon: BarChart2,
    label: "Agent 5 — Interest Scorer",
    desc: "Reads the full conversation transcript and scores each candidate's genuine interest and fit 0–100.",
    color: "bg-green-500/10 text-green-500 border-green-500/20",
  },
];

const STACK = [
  { label: "LLM", value: "Groq · Llama 3.3 70B" },
  { label: "Vector DB", value: "ChromaDB (ONNX embeddings)" },
  { label: "Backend", value: "FastAPI · Render" },
  { label: "Frontend", value: "Next.js · Vercel" },
];

export function SettingsModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-card w-full max-w-2xl rounded-xl shadow-xl overflow-hidden border border-border flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
          <div>
            <h2 className="text-xl font-semibold text-foreground flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              Architecture Overview
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              TalentRadar's 5-Agent AI Pipeline
            </p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-secondary rounded-full">
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-6">
          {/* Pipeline steps */}
          <div className="space-y-3">
            {AGENTS.map((agent, i) => {
              const Icon = agent.icon;
              return (
                <div
                  key={i}
                  className={`flex items-start gap-4 p-4 rounded-lg border ${agent.color}`}
                >
                  <div className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${agent.color}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground text-sm">{agent.label}</p>
                    <p className="text-muted-foreground text-sm mt-0.5">{agent.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Tech Stack */}
          <div>
            <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider mb-3">
              Tech Stack
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {STACK.map((item) => (
                <div key={item.label} className="p-3 bg-secondary rounded-lg border border-border">
                  <p className="text-xs text-muted-foreground font-medium">{item.label}</p>
                  <p className="text-sm font-semibold text-foreground mt-0.5">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
