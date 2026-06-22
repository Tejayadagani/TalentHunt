import { CandidateCard, CandidateResult } from "./CandidateCard";
import { motion } from "framer-motion";

import { Loader2 } from "lucide-react";

interface ShortlistTableProps {
  candidates: CandidateResult[];
  isLoading?: boolean;
  onStartInterview?: (candidate: CandidateResult) => void;
  interviewingId?: string | null;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  hideInterviewButton?: boolean;
}

export function ShortlistTable({ 
  candidates, 
  isLoading, 
  onStartInterview, 
  interviewingId,
  selectedIds,
  onToggleSelect,
  hideInterviewButton
}: ShortlistTableProps) {
  if (!candidates || candidates.length === 0) {
    if (isLoading) {
      return (
        <div className="text-center py-16 text-[#A0A0A0] border-2 border-dashed border-[#222] rounded-xl bg-[#1A1A1A]/40 backdrop-blur-xl">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3 text-[#D4AF37]" />
          <p className="text-[13px] font-medium text-white/80">Evaluating matches...</p>
          <p className="text-[12px] mt-1 text-[#666]">Candidates will appear here as they complete the pipeline.</p>
        </div>
      );
    }
    return (
      <div className="text-center py-12 text-[#A0A0A0] border-2 border-dashed border-[#333] rounded-xl bg-[#1A1A1A]/60 backdrop-blur-xl">
        No candidates found. Try adjusting your job description or relaxing the requirements.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {candidates.map((candidate, idx) => {
        const cid = candidate.id || (candidate as any).candidate_id || String(idx);
        return (
          <motion.div
            key={cid}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: idx * 0.08 }}
          >
            <CandidateCard 
              candidate={candidate} 
              onStartInterview={onStartInterview ? () => onStartInterview(candidate) : undefined}
              isInterviewing={interviewingId === cid}
              isSelected={selectedIds ? selectedIds.has(cid) : false}
              onSelectToggle={onToggleSelect ? () => onToggleSelect(cid) : undefined}
              hideInterviewButton={hideInterviewButton}
              isInterviewComplete={candidate.conversation_transcript && candidate.conversation_transcript.length > 0}
            />
          </motion.div>
        );
      })}
    </div>
  );
}
