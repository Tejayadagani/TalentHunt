import { CandidateCard, CandidateResult } from "./CandidateCard";
import { motion } from "framer-motion";

interface ShortlistTableProps {
  candidates: CandidateResult[];
}

export function ShortlistTable({ candidates }: ShortlistTableProps) {
  if (!candidates || candidates.length === 0) {
    return (
      <div className="text-center py-12 text-[#4A4A4A] border-2 border-dashed border-[#E0E0E0] rounded-xl bg-white">
        No candidates found. Try adjusting your job description or relaxing the requirements.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {candidates.map((candidate, idx) => (
        <motion.div
          key={candidate.id || idx}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: idx * 0.08 }}
        >
          <CandidateCard candidate={candidate} />
        </motion.div>
      ))}
    </div>
  );
}
