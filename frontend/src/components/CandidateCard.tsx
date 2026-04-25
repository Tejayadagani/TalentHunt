"use client";

import { useState, useEffect } from "react";
import { ConversationViewer, ConversationMessage } from "./ConversationViewer";
import { motion } from "framer-motion";
import { BookmarkCheck, Bookmark } from "lucide-react";

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

  // Note: omitting missing_skills and breakdowns from UI for simplicity, unless we pass them.
  // The API doesn't guarantee missing_skills directly on root, but we can check if it exists
  missing_skills?: string[];
}

interface CandidateCardProps {
  candidate: CandidateResult;
}

export function CandidateCard({ candidate }: CandidateCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const SAVED_KEY = "talentradar_saved_candidates";

  const isSavedForLater = (): boolean => {
    try {
      const raw = localStorage.getItem(SAVED_KEY);
      const list: string[] = raw ? JSON.parse(raw) : [];
      return list.includes(candidate.id);
    } catch { return false; }
  };

  const [savedLater, setSavedLater] = useState(false);

  useEffect(() => {
    setSavedLater(isSavedForLater());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidate.id]);

  const toggleSaveForLater = () => {
    try {
      const raw = localStorage.getItem(SAVED_KEY);
      const list: string[] = raw ? JSON.parse(raw) : [];
      const updated = list.includes(candidate.id)
        ? list.filter((id) => id !== candidate.id)
        : [...list, candidate.id];
      localStorage.setItem(SAVED_KEY, JSON.stringify(updated));
      setSavedLater(!savedLater);
    } catch { /* ignore */ }
  };

  const handleSendOffer = () => {
    const email = candidate.email || "";
    const subject = encodeURIComponent(
      `Exciting Opportunity — ${candidate.current_title} Role`
    );
    const body = encodeURIComponent(
`Hi ${candidate.name},

I came across your profile and I'm impressed by your experience as a ${candidate.current_title} at ${candidate.current_company} with ${candidate.years_of_experience} years of expertise.

We have an opening that we believe would be a great fit for your skills in ${candidate.skills.slice(0, 3).join(", ")}. We'd love to connect and discuss this opportunity with you.

Would you be available for a quick call this week?

Best regards`
    );
    window.location.href = `mailto:${email}?subject=${subject}&body=${body}`;
  };

  const getScoreColor = (score: number) => {
    if (score <= 40) return "bg-destructive";
    if (score <= 75) return "bg-accent";
    return "bg-primary";
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-card border border-border rounded-xl p-5 shadow-sm hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)] hover:border-t-accent transition-all duration-200"
    >
      <div className="flex flex-col gap-4">
        {/* Header: Rank, Name, Role */}
        <div className="flex justify-between items-start">
          <div className="flex gap-4">
            <div className="bg-primary text-primary-foreground font-bold text-[14px] px-3 py-1 rounded h-fit shrink-0">
              Rank #{candidate.rank}
            </div>
            <div>
              <h3 className="text-[16px] font-semibold text-foreground">
                {candidate.name}
              </h3>
              <p className="text-[14px] text-muted-foreground mt-0.5">
                {candidate.current_title} at {candidate.current_company} • {candidate.years_of_experience} years exp • {candidate.location} {candidate.remote_ok && "(Remote-ok)"}
              </p>
            </div>
          </div>
        </div>

        {/* Score Bars */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-y border-border py-4 my-2">
          {/* Match Score */}
          <div className="flex flex-col">
            <span className="text-[13px] font-bold text-foreground uppercase tracking-wide">Match Score</span>
            <span className="text-[28px] font-bold text-foreground leading-none my-1">{Math.round(candidate.match_score)}</span>
            <div className="h-3 w-full bg-secondary rounded-full overflow-hidden mt-1 border border-border">
              <div 
                className={`h-full ${getScoreColor(candidate.match_score)}`} 
                style={{ width: `${candidate.match_score}%` }}
              />
            </div>
          </div>
          
          {/* Interest Score */}
          <div className="flex flex-col">
            <span className="text-[13px] font-bold text-foreground uppercase tracking-wide">Interest Score</span>
            <span className="text-[28px] font-bold text-foreground leading-none my-1">{Math.round(candidate.interest_score)}</span>
            <div className="h-3 w-full bg-secondary rounded-full overflow-hidden mt-1 border border-border">
              <div 
                className={`h-full ${getScoreColor(candidate.interest_score)}`} 
                style={{ width: `${candidate.interest_score}%` }}
              />
            </div>
          </div>

          {/* Combined Score */}
          <div className="flex flex-col">
            <span className="text-[13px] font-bold text-accent uppercase tracking-wide">Combined Score</span>
            <span className="text-[28px] font-bold text-foreground leading-none my-1">{Math.round(candidate.combined_score)}</span>
            <div className="h-3 w-full bg-secondary rounded-full overflow-hidden mt-1 border border-border">
              <div 
                className="h-full bg-accent" 
                style={{ width: `${candidate.combined_score}%` }}
              />
            </div>
          </div>
        </div>

        {/* Skills */}
        <div className="flex flex-wrap gap-2 text-[13px]">
          <span className="text-muted-foreground self-center mr-1">Skills:</span>
          {candidate.skills.slice(0, 8).map(skill => (
            <span key={skill} className="bg-[rgba(45,125,62,0.1)] text-foreground border border-[rgba(45,125,62,0.2)] px-2 py-0.5 rounded-sm">
              {skill} ✓
            </span>
          ))}
          {candidate.skills.length > 8 && (
            <span className="text-muted-foreground self-center">+{candidate.skills.length - 8} more</span>
          )}
          
          {candidate.missing_skills && candidate.missing_skills.length > 0 && (
            <>
              <span className="text-muted-foreground self-center ml-2 mr-1">Missing:</span>
              {candidate.missing_skills.map(skill => (
                <span key={skill} className="text-muted-foreground line-through px-2 py-0.5">
                  {skill}
                </span>
              ))}
            </>
          )}
        </div>

        {/* Explanation */}
        <div className="text-[14px] text-muted-foreground italic leading-relaxed border-l-2 border-border pl-3 mt-2">
          &quot;{candidate.explanation}&quot;
        </div>

        {/* Match Reason (Secondary explanation from Agent 2) */}
        <div className="text-[13px] text-muted-foreground flex gap-4 mt-2">
          <span className="truncate max-w-[80%]"><strong>Match Reasoning:</strong> {candidate.match_reason}</span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 mt-4 pt-4 border-t border-border flex-wrap">
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className="border-2 border-primary bg-transparent text-primary hover:bg-[rgba(45,125,62,0.1)] font-semibold text-[14px] px-[22px] py-[10px] rounded-[6px] transition-all"
          >
            {isExpanded ? "Hide Conversation" : "View Conversation"}
          </button>
          
          <button
            onClick={handleSendOffer}
            disabled={!candidate.email}
            title={candidate.email ? `Send offer to ${candidate.email}` : "No email available"}
            className="bg-primary hover:bg-[#1F5A2B] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-[14px] px-[24px] py-[12px] rounded-[6px] shadow-sm transition-all active:scale-[0.98]"
          >
            Send Offer
          </button>

          <button
            onClick={toggleSaveForLater}
            className={`flex items-center gap-1.5 bg-transparent font-medium text-[14px] px-3 py-2 transition-all ${
              savedLater
                ? "text-primary"
                : "text-muted-foreground hover:text-primary"
            }`}
          >
            {savedLater
              ? <><BookmarkCheck className="w-4 h-4" /> Saved</>
              : <><Bookmark className="w-4 h-4" /> Save for later</>}
          </button>
        </div>

        {/* Expandable Conversation Viewer */}
        <ConversationViewer 
          transcript={candidate.conversation_transcript || []} 
          isOpen={isExpanded} 
          onClose={() => setIsExpanded(false)} 
        />
      </div>
    </motion.div>
  );
}
