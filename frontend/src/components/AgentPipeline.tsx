"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, FileSearch, Users, MessageSquare, Star, Zap, Trophy } from "lucide-react";

/* ── Agent definitions ───────────────────────────────────────────────────── */
const AGENTS = [
  { id: 1, label: "JD Parser",       sublabel: "Extract skills",        icon: FileSearch     },
  { id: 2, label: "Talent Scout",    sublabel: "Search talent pool",    icon: Users          },
  { id: 3, label: "Recruiter AI",    sublabel: "Outreach messages",     icon: MessageSquare  },
  { id: 4, label: "Candidate AI",    sublabel: "Candidate responses",   icon: Zap            },
  { id: 5, label: "Interest Scorer", sublabel: "Score & rank",          icon: Star           },
] as const;

/**
 * Layout — two horizontal rows:
 *
 *  Row 1:  [1] ──→ [2] ──→ [3]
 *                            │
 *  Row 2:          [4] ←────┘  [4] ──→ [5]
 *
 * Simpler to render as two separate rows with an SVG connector strip.
 */
const ROW1 = [1, 2, 3] as const;
const ROW2 = [4, 5]    as const;

/* ── Types ─────────────────────────────────────────────────────────────── */
interface AgentPipelineProps {
  activeAgent:    number; // 1–5, 0 = none yet
  completedCount: number;
  totalCandidates: number;
  message:        string;
}

type NodeStatus = "idle" | "active" | "done";

/* ── Helpers ────────────────────────────────────────────────────────────── */
function getStatus(id: number, active: number, completed: number): NodeStatus {
  const parallel = active >= 3 && (id === 3 || id === 4);
  const scorerActive = active >= 3 && id === 5 && completed > 0;
  if (id < active && !parallel)     return "done";
  if (id === active || parallel || scorerActive) return "active";
  if (id < active)                  return "done";
  return "idle";
}

/* ── Horizontal connector ─────────────────────────────────────────────── */
function HArrow({ done, active }: { done: boolean; active: boolean }) {
  const color = done ? "#2D7D3E" : active ? "#D4AF37" : "#2A2A2A";
  return (
    <div className="flex items-center shrink-0 w-16 px-1">
      {/* animated dots */}
      <div className="flex items-center gap-[4px] w-full">
        {[0, 1, 2, 3, 4].map((i) => (
          <motion.div
            key={i}
            className="flex-1 h-[3px] rounded-full"
            style={{ background: color }}
            animate={active ? { opacity: [0.3, 1, 0.3] } : { opacity: 1 }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
        {/* arrowhead */}
        <div
          className="w-0 h-0 shrink-0"
          style={{
            borderTop: "5px solid transparent",
            borderBottom: "5px solid transparent",
            borderLeft: `7px solid ${color}`,
          }}
        />
      </div>
    </div>
  );
}

/* ── Single node ────────────────────────────────────────────────────────── */
function AgentNode({ id, status }: { id: number; status: NodeStatus }) {
  const agent = AGENTS.find((a) => a.id === id)!;
  const Icon  = agent.icon;

  const border  = status === "done" ? "#2D7D3E" : status === "active" ? "#D4AF37" : "#222";
  const iconBg  = status === "done" ? "rgba(45,125,62,0.15)" : status === "active" ? "rgba(212,175,55,0.1)" : "rgba(20,20,20,0.8)";
  const iconClr = status === "done" ? "#4A9D5F" : status === "active" ? "#D4AF37" : "#444";
  const txtClr  = status === "done" ? "#fff" : status === "active" ? "#D4AF37" : "#666";

  return (
    <motion.div
      className="flex flex-col items-center gap-3 w-[110px] shrink-0"
      animate={status === "active" ? { y: [0, -5, 0] } : { y: 0 }}
      transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
    >
      {/* Glow */}
      <div className="relative">
        {status === "active" && (
          <motion.div
            className="absolute inset-[-12px] rounded-[1.5rem]"
            style={{ background: "radial-gradient(circle, rgba(212,175,55,0.2) 0%, transparent 70%)" }}
            animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        )}

        {/* Box */}
        <motion.div
          className="w-20 h-20 rounded-2xl flex items-center justify-center relative bg-clip-padding"
          style={{
            background: iconBg,
            border: `2px solid ${border}`,
            boxShadow:
              status === "active" ? "0 0 30px rgba(212,175,55,0.25)" :
              status === "done"   ? "0 0 20px rgba(45,125,62,0.15)"  : "none",
          }}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1,    opacity: 1 }}
          transition={{ duration: 0.4, delay: id * 0.08 }}
        >
          {status === "done" ? (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 200 }}>
              <Check className="w-8 h-8 text-[#4A9D5F]" strokeWidth={3} />
            </motion.div>
          ) : status === "active" ? (
            <Loader2 className="w-8 h-8 text-[#D4AF37] animate-spin" />
          ) : (
            <Icon className="w-7 h-7" style={{ color: iconClr }} />
          )}

          {/* Badge */}
          <div
            className="absolute -top-2.5 -right-2.5 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-black shadow-lg"
            style={{
              background: status === "active" ? "#D4AF37" : status === "done" ? "#2D7D3E" : "#1A1A1A",
              color: status === "idle" ? "#555" : "#000",
              border: `2px solid ${status === "idle" ? border : "#0D0D0D"}`,
            }}
          >
            {agent.id}
          </div>
        </motion.div>
      </div>

      {/* Label */}
      <div className="flex flex-col items-center">
        <p className="text-[13px] font-bold text-center leading-tight tracking-wide" style={{ color: txtClr }}>
          {agent.label}
        </p>
        <p className="text-[11px] text-center leading-tight mt-1" style={{ color: status === "idle" ? "#333" : "#888" }}>
          {agent.sublabel}
        </p>
      </div>
    </motion.div>
  );
}

/* ── Vertical connector between rows ──────────────────────────────────── */
function VConnector({ active }: { active: boolean }) {
  const color = active ? "#D4AF37" : "#2A2A2A";
  return (
    <div className="flex flex-col items-center gap-[4px] py-1" style={{ height: 48 }}>
      {[0, 1, 2, 3].map((i) => (
        <motion.div
          key={i}
          className="w-[3px] flex-1 rounded-full"
          style={{ background: color }}
          animate={active ? { opacity: [0.3, 1, 0.3] } : { opacity: 1 }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
      {/* Down arrow head */}
      <div
        className="w-0 h-0 shrink-0"
        style={{
          borderLeft: "5px solid transparent",
          borderRight: "5px solid transparent",
          borderTop: `7px solid ${color}`,
        }}
      />
    </div>
  );
}

/* ── Main component ─────────────────────────────────────────────────────── */
export function AgentPipeline({ activeAgent, completedCount, totalCandidates, message }: AgentPipelineProps) {
  const s = (id: number) => getStatus(id, activeAgent, completedCount);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[#0D0D0D]/90 backdrop-blur-xl rounded-2xl shadow-2xl overflow-hidden w-full"
      style={{ border: "1px solid #1A1A1A" }}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-[#141414] flex items-center gap-2">
        <Trophy className="w-4 h-4 text-[#D4AF37]" />
        <h2 className="text-[13px] font-bold text-white tracking-wide">Multi-Agent Pipeline</h2>
        <span className="ml-auto text-[10px] text-[#333] font-mono">5 agents</span>
      </div>

      {/* ── Pipeline canvas ── */}
      <div className="px-5 pt-10 pb-8 overflow-x-auto hide-scrollbar">
        <div className="relative mx-auto" style={{ width: 632 }}>
          
          {/* Row 1: Agents 1 → 2 → 3 */}
          <div className="flex items-start absolute top-0 left-0">
            {ROW1.map((id, i) => (
              <div key={id} className="flex items-start">
                <AgentNode id={id} status={s(id)} />
                {i < ROW1.length - 1 && (
                  <div className="mt-10 -translate-y-1/2">
                    <HArrow
                      done={s(id) === "done" && s(ROW1[i + 1]) !== "idle"}
                      active={s(id) === "active" || s(ROW1[i + 1]) === "active"}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Bend connector: drops straight down from Agent 3 to Agent 4 */}
          <div className="absolute left-[348px]" style={{ top: 84 }}>
            <div className="w-[110px] flex justify-center">
               <VConnector active={s(3) !== "idle" || s(4) !== "idle"} />
            </div>
          </div>

          {/* Row 2: Agents 4 → 5 */}
          <div className="flex items-start absolute left-[348px]" style={{ top: 138 }}>
            {ROW2.map((id, i) => (
              <div key={id} className="flex items-start">
                <AgentNode id={id} status={s(id)} />
                {i < ROW2.length - 1 && (
                  <div className="mt-10 -translate-y-1/2">
                    <HArrow
                      done={s(id) === "done" && s(ROW2[i + 1]) !== "idle"}
                      active={s(id) === "active" || s(ROW2[i + 1]) === "active"}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Spacer to give the relative container height */}
          <div style={{ height: 260 }} />
        </div>
      </div>

      {/* Status + progress */}
      <div className="px-5 pb-5 space-y-3">
        <div
          className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl"
          style={{ background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.12)" }}
        >
          <Loader2 className="w-3.5 h-3.5 text-[#D4AF37] animate-spin shrink-0" />
          <span className="text-[11px] font-medium text-[#C8A830] leading-snug">{message || "Initializing..."}</span>
        </div>

        <AnimatePresence>
          {totalCandidates > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div className="flex justify-between text-[10px] mb-1" style={{ color: "#444" }}>
                <span>Candidates evaluated</span>
                <span className="font-bold text-[#4A9D5F]">{completedCount} / {totalCandidates}</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "#141414" }}>
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: "linear-gradient(90deg, #1F5A2B, #4A9D5F)" }}
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
