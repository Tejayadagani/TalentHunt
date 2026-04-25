import { CandidateCard, CandidateResult } from "./CandidateCard";
import { motion } from "framer-motion";

interface ShortlistTableProps {
  candidates: CandidateResult[];
}

export function ShortlistTable({ candidates }: ShortlistTableProps) {
  if (!candidates || candidates.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground border border-dashed border-border rounded-lg">
        No candidates found. Try adjusting your job description or relaxing the requirements.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {candidates.map((candidate, idx) => (
        <motion.div
          key={candidate.id || idx}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: idx * 0.1 }}
        >
          <CandidateCard candidate={candidate} />
        </motion.div>
      ))}
    </div>
  );
}
