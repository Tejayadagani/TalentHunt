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
        className="bg-[#1A1A1A]/90 backdrop-blur-xl w-full max-w-2xl rounded-xl shadow-2xl overflow-hidden border border-[#333] flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[#333]">
          <div>
            <h2 className="text-[18px] font-bold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              Architecture Overview
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              SkillSync AI&apos;s 5-Agent AI Pipeline
            </p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-[#333] rounded-full transition-colors">
            <X className="w-5 h-5 text-[#A0A0A0]" />
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
                    <h3 className="font-semibold text-white text-[13px]">{agent.label}</h3>
                    <p className="text-[12px] text-[#A0A0A0] mt-0.5">{agent.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Tech Stack */}
          <div className="bg-[#0A0A0A] border border-[#333] rounded-lg p-5">
            <h3 className="text-[13px] font-bold text-white uppercase tracking-wider mb-4">Tech Stack</h3>
            <div className="grid grid-cols-2 gap-4">
              {STACK.map((item) => (
                <div key={item.label} className="flex flex-col gap-1">
                  <span className="text-[11px] text-[#777] uppercase tracking-wide font-medium">{item.label}</span>
                  <span className="text-[13px] font-medium text-white">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
