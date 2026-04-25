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
  const color = done ? "#2D7D3E" : active ? "#D4AF37" : "#222";
  return (
    <div className="flex items-center shrink-0 w-8">
      {/* animated dots */}
      <div className="flex items-center gap-[3px] w-full">
        {[0, 1, 2, 3].map((i) => (
          <motion.div
            key={i}
            className="flex-1 h-[2px] rounded-full"
            style={{ background: color }}
            animate={active ? { opacity: [0.3, 1, 0.3] } : { opacity: 1 }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
        {/* arrowhead */}
        <div
          className="w-0 h-0 shrink-0"
          style={{
            borderTop: "4px solid transparent",
            borderBottom: "4px solid transparent",
            borderLeft: `5px solid ${color}`,
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

  const border  = status === "done" ? "#2D7D3E" : status === "active" ? "#D4AF37" : "#1E1E1E";
  const iconBg  = status === "done" ? "rgba(45,125,62,0.18)" : status === "active" ? "rgba(212,175,55,0.12)" : "rgba(20,20,20,0.9)";
  const iconClr = status === "done" ? "#4A9D5F" : status === "active" ? "#D4AF37" : "#333";
  const txtClr  = status === "done" ? "#fff" : status === "active" ? "#D4AF37" : "#3A3A3A";

  return (
    <motion.div
      className="flex flex-col items-center gap-1.5 w-[88px] shrink-0"
      animate={status === "active" ? { y: [0, -3, 0] } : { y: 0 }}
      transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
    >
      {/* Glow */}
      <div className="relative">
        {status === "active" && (
          <motion.div
            className="absolute inset-[-6px] rounded-2xl"
            style={{ background: "radial-gradient(circle, rgba(212,175,55,0.18) 0%, transparent 70%)" }}
            animate={{ scale: [1, 1.25, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        )}

        {/* Box */}
        <motion.div
          className="w-14 h-14 rounded-xl flex items-center justify-center relative"
          style={{
            background: iconBg,
            border: `1.5px solid ${border}`,
            boxShadow:
              status === "active" ? "0 0 18px rgba(212,175,55,0.25)" :
              status === "done"   ? "0 0 10px rgba(45,125,62,0.18)"  : "none",
          }}
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1,    opacity: 1 }}
          transition={{ duration: 0.35, delay: id * 0.06 }}
        >
          {status === "done" ? (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 200 }}>
              <Check className="w-5 h-5 text-[#4A9D5F]" strokeWidth={2.5} />
            </motion.div>
          ) : status === "active" ? (
            <Loader2 className="w-5 h-5 text-[#D4AF37] animate-spin" />
          ) : (
            <Icon className="w-5 h-5" style={{ color: iconClr }} />
          )}

          {/* Badge */}
          <div
            className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold"
            style={{
              background: status === "active" ? "#D4AF37" : status === "done" ? "#2D7D3E" : "#181818",
              color: status === "idle" ? "#333" : "#fff",
              border: `1px solid ${border}`,
            }}
          >
            {agent.id}
          </div>
        </motion.div>
      </div>

      {/* Label */}
      <p className="text-[10px] font-bold text-center leading-tight" style={{ color: txtClr }}>
        {agent.label}
      </p>
      <p className="text-[9px] text-center leading-tight" style={{ color: status === "idle" ? "#282828" : "#555" }}>
        {agent.sublabel}
      </p>
    </motion.div>
  );
}

/* ── Vertical connector between rows ──────────────────────────────────── */
function VConnector({ active }: { active: boolean }) {
  const color = active ? "#D4AF37" : "#1E1E1E";
  return (
    <div className="flex flex-col items-center" style={{ height: 28 }}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-[2px] flex-1 rounded-full"
          style={{ background: color }}
          animate={active ? { opacity: [0.3, 1, 0.3] } : { opacity: 1 }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
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
      <div className="px-5 pt-6 pb-4">

        {/* Row 1: Agents 1 → 2 → 3 */}
        <div className="flex items-start">
          {ROW1.map((id, i) => (
            <div key={id} className="flex items-center">
              <AgentNode id={id} status={s(id)} />
              {i < ROW1.length - 1 && (
                <HArrow
                  done={s(id) === "done" && s(ROW1[i + 1]) !== "idle"}
                  active={s(id) === "active" || s(ROW1[i + 1]) === "active"}
                />
              )}
            </div>
          ))}

          {/* Gap then agents 4→5 on row 2 below, connected by a bend */}
        </div>

        {/* Bend connector: drops from Agent 3 down to Agent 4 */}
        <div className="flex items-start" style={{ paddingLeft: 196 }}>
          <VConnector active={s(3) !== "idle" || s(4) !== "idle"} />
        </div>

        {/* Row 2: Agents 4 → 5 */}
        <div className="flex items-start" style={{ paddingLeft: 152 }}>
          {ROW2.map((id, i) => (
            <div key={id} className="flex items-center">
              <AgentNode id={id} status={s(id)} />
              {i < ROW2.length - 1 && (
                <HArrow
                  done={s(id) === "done" && s(ROW2[i + 1]) !== "idle"}
                  active={s(id) === "active" || s(ROW2[i + 1]) === "active"}
                />
              )}
            </div>
          ))}
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
