"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, FileSearch, Users, MessageSquare, Star, Trophy, Zap } from "lucide-react";

export interface AgentStep {
  id: number;
  label: string;
  sublabel: string;
  icon: React.ElementType;
}

const AGENTS: AgentStep[] = [
  { id: 1, label: "JD Parser",       sublabel: "Extract skills & seniority",     icon: FileSearch     },
  { id: 2, label: "Talent Scout",    sublabel: "Semantic search in talent pool",  icon: Users          },
  { id: 3, label: "Recruiter AI",    sublabel: "Simulate outreach messages",      icon: MessageSquare  },
  { id: 4, label: "Candidate AI",    sublabel: "Simulate candidate responses",    icon: Zap            },
  { id: 5, label: "Interest Scorer", sublabel: "Score & rank final results",      icon: Star           },
];

interface AgentPipelineProps {
  activeAgent: number;   // 1-5, 0 = none yet
  completedCount: number; // number of candidates returned so far
  totalCandidates: number;
  message: string;
}

function NodeConnector({ done }: { done: boolean }) {
  return (
    <div className="flex flex-col items-center gap-0 shrink-0">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-0.5 h-2 rounded-full"
          style={{ background: done ? "#2D7D3E" : "#2A2A2A" }}
          animate={{ opacity: done ? 1 : [0.3, 0.8, 0.3] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  );
}

function AgentNode({
  agent,
  status,
  isLast,
}: {
  agent: AgentStep;
  status: "idle" | "active" | "done";
  isLast: boolean;
}) {
  const Icon = agent.icon;

  const borderColor =
    status === "done"   ? "#2D7D3E" :
    status === "active" ? "#D4AF37" :
    "#2A2A2A";

  const iconBg =
    status === "done"   ? "rgba(45,125,62,0.2)"  :
    status === "active" ? "rgba(212,175,55,0.15)" :
    "rgba(30,30,30,0.8)";

  const iconColor =
    status === "done"   ? "#4A9D5F" :
    status === "active" ? "#D4AF37" :
    "#444";

  const labelColor =
    status === "done"   ? "#ffffff" :
    status === "active" ? "#D4AF37" :
    "#555";

  return (
    <div className="flex flex-col items-center gap-0">
      {/* Node */}
      <motion.div
        className="relative flex flex-col items-center"
        animate={status === "active" ? { y: [0, -2, 0] } : { y: 0 }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
      >
        {/* Glow for active */}
        {status === "active" && (
          <motion.div
            className="absolute inset-0 rounded-2xl"
            style={{ background: "radial-gradient(circle at center, rgba(212,175,55,0.15) 0%, transparent 70%)" }}
            animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        )}

        <motion.div
          className="w-16 h-16 rounded-2xl flex items-center justify-center relative shadow-lg"
          style={{
            background: iconBg,
            border: `1.5px solid ${borderColor}`,
            boxShadow: status === "active" ? `0 0 20px rgba(212,175,55,0.3)` :
                       status === "done"   ? `0 0 12px rgba(45,125,62,0.2)` : "none",
          }}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          {status === "done" ? (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 200 }}>
              <Check className="w-7 h-7 text-[#4A9D5F]" strokeWidth={2.5} />
            </motion.div>
          ) : status === "active" ? (
            <Loader2 className="w-7 h-7 text-[#D4AF37] animate-spin" />
          ) : (
            <Icon className="w-6 h-6" style={{ color: iconColor }} />
          )}

          {/* Agent number badge */}
          <div
            className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
            style={{
              background: status === "active" ? "#D4AF37" : status === "done" ? "#2D7D3E" : "#222",
              color: status === "idle" ? "#555" : "#fff",
              border: `1px solid ${borderColor}`,
            }}
          >
            {agent.id}
          </div>
        </motion.div>

        {/* Label */}
        <div className="mt-2.5 text-center w-20">
          <p className="text-[11px] font-bold leading-tight" style={{ color: labelColor }}>
            {agent.label}
          </p>
          <p className="text-[9px] mt-0.5 leading-tight" style={{ color: status === "idle" ? "#333" : "#666" }}>
            {agent.sublabel}
          </p>
        </div>
      </motion.div>

      {/* Connector below */}
      {!isLast && <NodeConnector done={status === "done"} />}
    </div>
  );
}

export function AgentPipeline({ activeAgent, completedCount, totalCandidates, message }: AgentPipelineProps) {
  const getStatus = (agentId: number): "idle" | "active" | "done" => {
    if (agentId < activeAgent) return "done";
    if (agentId === activeAgent) return "active";
    // Agents 4 and 5 activate with agent 3 since they run in parallel
    if (activeAgent >= 3 && agentId === 4) return "active";
    if (activeAgent >= 3 && completedCount > 0 && agentId === 5) return "active";
    return "idle";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[#111]/80 backdrop-blur-xl rounded-2xl shadow-2xl overflow-hidden"
      style={{ border: "1px solid #222" }}
    >
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-[#1A1A1A]">
        <div className="flex items-center gap-2 mb-1">
          <Trophy className="w-4 h-4 text-[#D4AF37]" />
          <h2 className="text-[15px] font-bold text-white">Multi-Agent Pipeline</h2>
        </div>
        <p className="text-[12px] text-[#555]">5 AI agents working in sequence to find your best candidates</p>
      </div>

      {/* Pipeline nodes */}
      <div className="flex flex-col items-center py-8 px-6">
        {AGENTS.map((agent, i) => (
          <AgentNode
            key={agent.id}
            agent={agent}
            status={getStatus(agent.id)}
            isLast={i === AGENTS.length - 1}
          />
        ))}
      </div>

      {/* Status footer */}
      <div className="px-6 pb-5">
        <div
          className="flex items-center gap-2.5 px-4 py-3 rounded-xl"
          style={{ background: "rgba(212,175,55,0.07)", border: "1px solid rgba(212,175,55,0.15)" }}
        >
          <Loader2 className="w-3.5 h-3.5 text-[#D4AF37] animate-spin shrink-0" />
          <span className="text-[12px] font-medium text-[#D4AF37] leading-snug">{message || "Initializing..."}</span>
        </div>

        {/* Progress bar for candidates */}
        <AnimatePresence>
          {totalCandidates > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mt-3"
            >
              <div className="flex justify-between text-[10px] mb-1.5" style={{ color: "#555" }}>
                <span>Candidates evaluated</span>
                <span className="text-[#4A9D5F] font-bold">{completedCount} / {totalCandidates}</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "#1A1A1A" }}>
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: "linear-gradient(90deg, #2D7D3E, #4A9D5F)" }}
                  initial={{ width: 0 }}
                  animate={{ width: `${totalCandidates > 0 ? (completedCount / totalCandidates) * 100 : 0}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
