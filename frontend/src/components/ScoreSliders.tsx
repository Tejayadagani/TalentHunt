"use client";

import { useState } from "react";
import { CandidateResult } from "./CandidateCard";
import { Check } from "lucide-react";

interface ScoreSlidersProps {
  initialMatchWeight: number;
  shortlist: CandidateResult[];
  onReRank: (newShortlist: CandidateResult[], newWeight: number) => void;
}

export function ScoreSliders({ initialMatchWeight, shortlist, onReRank }: ScoreSlidersProps) {
  const [matchWeight, setMatchWeight] = useState(initialMatchWeight);
  const [reranked, setReranked] = useState(false);

  const applyReRank = () => {
    const interestWeight = 1 - matchWeight;
    const sorted = shortlist
      .map(c => ({ ...c, combined_score: c.match_score * matchWeight + c.interest_score * interestWeight }))
      .sort((a, b) => b.combined_score - a.combined_score)
      .map((c, i) => ({ ...c, rank: i + 1 }));
    onReRank(sorted, matchWeight);
    setReranked(true);
    setTimeout(() => setReranked(false), 2000);
  };

  return (
    <div className="bg-[#1A1A1A]/60 backdrop-blur-xl border border-[#333] rounded-xl p-5 shadow-lg">
      <h3 className="text-[13px] font-bold text-white uppercase tracking-wide mb-4">
        Adjust ranking weights (optional)
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-5">
        {/* Match weight */}
        <div>
          <div className="flex justify-between text-[13px] font-medium text-white mb-2">
            <span>Match score weight</span>
            <span className="font-bold text-[#2D7D3E]">{Math.round(matchWeight * 100)}%</span>
          </div>
          <div className="relative flex items-center h-5">
            <div className="absolute w-full h-2 rounded-full" style={{ background: "#333" }} />
            <div
              className="absolute h-2 rounded-full"
              style={{ width: `${matchWeight * 100}%`, background: "#2D7D3E" }}
            />
            <input
              type="range" min={0} max={100} step={5}
              value={Math.round(matchWeight * 100)}
              onChange={e => setMatchWeight(Number(e.target.value) / 100)}
              className="absolute w-full h-2 appearance-none bg-transparent cursor-pointer"
              style={{ accentColor: "#2D7D3E" }}
            />
          </div>
        </div>

        {/* Interest weight */}
        <div>
          <div className="flex justify-between text-[13px] font-medium text-white mb-2">
            <span>Interest score weight</span>
            <span className="font-bold text-[#4A9D5F]">{Math.round((1 - matchWeight) * 100)}%</span>
          </div>
          <div className="relative flex items-center h-5">
            <div className="absolute w-full h-2 rounded-full" style={{ background: "#333" }} />
            <div
              className="absolute h-2 rounded-full"
              style={{ width: `${(1 - matchWeight) * 100}%`, background: "#4A9D5F" }}
            />
            <input
              type="range" min={0} max={100} step={5}
              value={Math.round((1 - matchWeight) * 100)}
              onChange={e => setMatchWeight(1 - Number(e.target.value) / 100)}
              className="absolute w-full h-2 appearance-none bg-transparent cursor-pointer"
              style={{ accentColor: "#4A9D5F" }}
            />
          </div>
        </div>
      </div>

      <button
        onClick={applyReRank}
        className={`h-10 px-6 rounded-lg border-2 text-[13px] font-semibold transition-all active:scale-[0.97] ${
          reranked
            ? "border-[#4A9D5F] bg-[#1A3A22]/50 text-[#4A9D5F]"
            : "border-[#4A9D5F] text-[#4A9D5F] hover:bg-[#1A3A22]/50"
        }`}
      >
        {reranked ? <><Check className="w-4 h-4" /> Re-ranked!</> : "Re-rank candidates"}
      </button>
    </div>
  );
}
