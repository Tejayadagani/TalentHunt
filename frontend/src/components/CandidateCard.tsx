"use client";

import { useState, useEffect } from "react";
import { ConversationViewer, ConversationMessage } from "./ConversationViewer";
import { motion } from "framer-motion";
import { BookmarkCheck, Bookmark, Mail, Check } from "lucide-react";

export interface CandidateResult {
  rank: number;
  id: string;
  name: string;
  current_title: string;
  current_company: string;
  seniority: string;
  years_of_experience: number;
  location: string;
  remote_ok: boolean;
  skills: string[];
  email?: string;
  match_score: number;
  match_reason: string;
  interest_score: number;
  combined_score: number;
  explanation: string;
  conversation_transcript: ConversationMessage[];
  missing_skills?: string[];
}

const SAVED_KEY = "talentradar_saved_candidates";

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-2 w-full rounded-full overflow-hidden" style={{ background: "#333" }}>
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${value}%`, background: color }} />
    </div>
  );
}

export function CandidateCard({ 
  candidate,
  onStartInterview,
  isInterviewing,
  isSelected,
  onSelectToggle,
  hideInterviewButton,
  isInterviewComplete
}: { 
  candidate: CandidateResult;
  onStartInterview?: () => void;
  isInterviewing?: boolean;
  isSelected?: boolean;
  onSelectToggle?: () => void;
  hideInterviewButton?: boolean;
  isInterviewComplete?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [savedLater, setSavedLater] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SAVED_KEY);
      const list: string[] = raw ? JSON.parse(raw) : [];
      setSavedLater(list.includes(candidate.id));
    } catch { /* ignore */ }
  }, [candidate.id]);

  const toggleSaveForLater = () => {
    try {
      const raw = localStorage.getItem(SAVED_KEY);
      const list: string[] = raw ? JSON.parse(raw) : [];
      const updated = list.includes(candidate.id)
        ? list.filter(id => id !== candidate.id)
        : [...list, candidate.id];
      localStorage.setItem(SAVED_KEY, JSON.stringify(updated));
      setSavedLater(!savedLater);
    } catch { /* ignore */ }
  };

  const handleSendOffer = () => {
    const email = candidate.email || "";
    const subject = encodeURIComponent(`Exciting opportunity — ${candidate.current_title} role`);
    const body = encodeURIComponent(
`Hi ${candidate.name},

I came across your profile and I'm impressed by your experience as a ${candidate.current_title} at ${candidate.current_company} with ${candidate.years_of_experience} years of expertise.

We have an opening that we believe is a strong match for your skills in ${candidate.skills.slice(0, 3).join(", ")}. We'd love to connect and share more details.

Would you be available for a quick call this week?

Best regards`
    );
    window.location.href = `mailto:${email}?subject=${subject}&body=${body}`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[#1A1A1A]/60 backdrop-blur-xl rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 overflow-hidden"
      style={{ border: "1px solid #333", borderTop: "3px solid #D4AF37" }}
      whileHover={{ y: -2 }}
    >
      {/* ── Header ── */}
      <div className="flex items-start gap-4 p-5 pb-4 cursor-pointer" onClick={onSelectToggle}>
        {onSelectToggle && (
          <div className="shrink-0 mt-2">
            <input 
              type="checkbox" 
              checked={!!isSelected}
              onChange={() => {}} // Handled by parent div click
              className="w-5 h-5 rounded border-[#4A9D5F] bg-[#1A1A1A] text-[#4A9D5F] focus:ring-[#4A9D5F] focus:ring-offset-[#0A0A0A] cursor-pointer"
            />
          </div>
        )}
        <div className="w-9 h-9 rounded-full bg-[#2D7D3E] flex items-center justify-center shrink-0 text-white text-[13px] font-bold shadow-sm">
          #{candidate.rank}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-[17px] font-bold text-white leading-tight">{candidate.name}</h3>
          <p className="text-[13px] text-[#A0A0A0] mt-0.5">
            {candidate.current_title} · {candidate.current_company} · {candidate.years_of_experience} yrs · {candidate.location}
            {candidate.remote_ok && <span className="ml-1.5 text-[#4A9D5F] font-medium">(Remote ok)</span>}
          </p>
        </div>
      </div>

      {/* ── Scores ── */}
      <div className="grid grid-cols-3 gap-4 px-5 py-4 border-t border-b border-[#333]">
        {/* Match */}
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-white mb-1">Match score</p>
          <p className="text-[28px] font-bold text-[#4A9D5F] leading-none mb-2">{Math.round(candidate.match_score)}</p>
          <ScoreBar value={candidate.match_score} color="#4A9D5F" />
        </div>
        {/* Interest */}
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-white mb-1">Interest score</p>
          <p className="text-[28px] font-bold text-[#4A9D5F] leading-none mb-2">{Math.round(candidate.interest_score)}</p>
          <ScoreBar value={candidate.interest_score} color="#4A9D5F" />
        </div>
        {/* Combined */}
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-[#D4AF37] mb-1">Combined score</p>
          <p className="text-[28px] font-bold text-[#D4AF37] leading-none mb-2">{Math.round(candidate.combined_score)}</p>
          <ScoreBar value={candidate.combined_score} color="#D4AF37" />
        </div>
      </div>

      {/* ── Skills ── */}
      <div className="px-5 py-4 flex flex-wrap gap-2">
        {candidate.skills.slice(0, 8).map(skill => (
          <span key={skill} className="flex items-center gap-1 text-[12px] px-3 py-1 rounded-md font-medium" style={{ background: "rgba(45,125,62,0.2)", color: "#4A9D5F" }}>
            {skill} <Check className="w-3 h-3 text-[#4A9D5F]" />
          </span>
        ))}
        {candidate.skills.length > 8 && (
          <span className="text-[12px] text-[#A0A0A0] self-center">+{candidate.skills.length - 8} more</span>
        )}
        {candidate.missing_skills && candidate.missing_skills.length > 0 && (
          candidate.missing_skills.map(skill => (
            <span key={skill} className="text-[12px] px-3 py-1 rounded-md text-[#777] line-through" style={{ background: "#333" }}>
              {skill}
            </span>
          ))
        )}
      </div>

      {/* ── Explanation ── */}
      <div className="px-5 pb-4">
        <p
          className="text-[13px] text-[#A0A0A0] italic leading-relaxed pl-4 line-clamp-3"
          style={{ borderLeft: "2px solid #D4AF37" }}
        >
          &ldquo;{candidate.explanation}&rdquo;
        </p>
        {candidate.match_reason && (
          <p className="text-[12px] text-[#A0A0A0] mt-2 truncate">
            <strong className="text-white">Match reasoning:</strong> {candidate.match_reason}
          </p>
        )}
      </div>

      {/* ── Actions ── */}
      <div className="flex flex-wrap items-center gap-2 px-5 py-4 border-t border-[#333] bg-[#0A0A0A]/50">
        {(!candidate.conversation_transcript || candidate.conversation_transcript.length === 0) ? (
          !hideInterviewButton && (
            <button
              onClick={onStartInterview}
              disabled={isInterviewing}
              className={`h-10 px-5 rounded-lg border-2 font-semibold text-[13px] transition-all flex items-center gap-2
                ${isInterviewing ? 'border-[#D4AF37] text-[#D4AF37] opacity-70 cursor-not-allowed' : 'border-[#4A9D5F] text-[#4A9D5F] hover:bg-[#1A3A22]/50 active:scale-[0.97]'}`}
            >
              {isInterviewing ? "Interviewing..." : "Send Interview"}
            </button>
          )
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}
            className="h-10 px-5 rounded-lg border-2 border-[#4A9D5F] text-[#4A9D5F] hover:bg-[#1A3A22]/50 font-semibold text-[13px] transition-all active:scale-[0.97]"
          >
            {isExpanded ? "Hide conversation" : "View conversation"}
          </button>
        )}

        <button
          onClick={(e) => { e.stopPropagation(); handleSendOffer(); }}
          disabled={!isInterviewComplete}
          title={!isInterviewComplete ? "Complete interview first" : "Send offer email"}
          className="h-10 px-5 rounded-lg bg-[#2D7D3E] hover:bg-[#1F5A2B] disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-[13px] transition-all active:scale-[0.97] flex items-center gap-1.5"
        >
          <Mail className="w-3.5 h-3.5" />
          Send offer
        </button>

        <button
          onClick={(e) => { e.stopPropagation(); toggleSaveForLater(); }}
          className={`h-10 px-4 rounded-lg text-[13px] font-medium flex items-center gap-1.5 transition-all ${
            savedLater ? "text-[#4A9D5F] bg-[#1A3A22]/50" : "text-[#A0A0A0] hover:text-white hover:bg-[#333]"
          }`}
        >
          {savedLater ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
          {savedLater ? "Saved" : "Save for later"}
        </button>
      </div>

      {/* ── Conversation ── */}
      <ConversationViewer
        transcript={candidate.conversation_transcript || []}
        isOpen={isExpanded}
        onClose={() => setIsExpanded(false)}
      />
    </motion.div>
  );
}
