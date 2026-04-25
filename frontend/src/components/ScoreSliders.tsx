"use client";

import { useState } from "react";
import { Slider } from "@/components/ui/slider";
import { CandidateResult } from "./CandidateCard";

interface ScoreSlidersProps {
  initialMatchWeight: number;
  shortlist: CandidateResult[];
  onReRank: (newShortlist: CandidateResult[], newWeight: number) => void;
}

export function ScoreSliders({ initialMatchWeight, shortlist, onReRank }: ScoreSlidersProps) {
  const [matchWeight, setMatchWeight] = useState(initialMatchWeight);

  const handleSliderChange = (vals: number | readonly number[]) => {
    const newMatchWeight = typeof vals === "number" ? vals : vals[0];
    setMatchWeight(newMatchWeight);
  };

  const applyReRank = () => {
    const interestWeight = 1 - matchWeight;

    // Recalculate combined scores and sort pure JS
    const reRanked = shortlist.map(c => {
      const combined = (c.match_score * matchWeight) + (c.interest_score * interestWeight);
      return {
        ...c,
        combined_score: combined
      };
    }).sort((a, b) => b.combined_score - a.combined_score);

    // Update ranks
    reRanked.forEach((c, index) => {
      c.rank = index + 1;
    });

    onReRank(reRanked, matchWeight);
  };

  return (
    <div className="bg-card border border-border rounded-lg p-5 shadow-sm space-y-4 mb-6">
      <h3 className="text-[16px] font-semibold text-foreground border-b border-border pb-2">
        Adjust ranking weights
      </h3>
      
      <div className="space-y-4 pt-2">
        {/* Match Score Weight Slider */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-[13px] font-bold text-foreground uppercase tracking-wide">
            <span>Match Score Weight</span>
            <span>{Math.round(matchWeight * 100)}%</span>
          </div>
          <Slider
            value={[matchWeight]}
            min={0}
            max={1}
            step={0.1}
            onValueChange={handleSliderChange}
            className="[&_[role=slider]]:bg-primary [&_[role=slider]]:border-primary"
          />
        </div>

        {/* Interest Score Weight Display */}
        <div className="space-y-2 opacity-80 pointer-events-none">
          <div className="flex justify-between items-center text-[13px] font-bold text-foreground uppercase tracking-wide">
            <span>Interest Score Weight</span>
            <span>{Math.round((1 - matchWeight) * 100)}%</span>
          </div>
          <Slider
            value={[1 - matchWeight]}
            min={0}
            max={1}
            step={0.1}
            className="[&_[role=slider]]:bg-[#A0A0A0] [&_[role=slider]]:border-[#A0A0A0]"
          />
        </div>
      </div>

      <div className="pt-2">
        <button 
          onClick={applyReRank}
          className="w-full sm:w-auto border-2 border-primary bg-transparent text-primary hover:bg-[rgba(45,125,62,0.1)] font-semibold text-[14px] px-[22px] py-[8px] rounded-[6px] transition-all active:scale-[0.98]"
        >
          Re-rank Candidates
        </button>
      </div>
    </div>
  );
}
