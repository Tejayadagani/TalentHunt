"use client";

import { useState } from "react";

export interface ScoutFormData {
  jd_text: string;
  top_k: number;
  match_weight: number;
  conversation_turns: number;
}

interface JDInputProps {
  onSubmit: (data: ScoutFormData) => void;
  isLoading: boolean;
}

export function JDInput({ onSubmit, isLoading }: JDInputProps) {
  const [jdText, setJdText] = useState("");
  const [topK, setTopK] = useState(5);
  const [matchWeight, setMatchWeight] = useState(0.6);
  const [turns, setTurns] = useState(4);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const charCount = jdText.length;
  const isReady = charCount >= 50 && !isLoading;

  const readiness =
    charCount === 0 ? ""
    : charCount < 50 ? `${charCount} characters · Add more detail`
    : charCount < 300 ? `${charCount} characters · Good to go`
    : `${charCount} characters · Ready to scout ✓`;

  const handleSubmit = () => {
    if (!isReady) return;
    onSubmit({ jd_text: jdText, top_k: topK, match_weight: matchWeight, conversation_turns: turns });
  };

  return (
    <div className="bg-white border border-[#E0E0E0] rounded-xl shadow-sm overflow-hidden">
      <div className="p-5">
        <label className="block text-[13px] font-bold text-[#1A1A1A] uppercase tracking-wide mb-3">
          Job description
        </label>
        <textarea
          value={jdText}
          onChange={e => setJdText(e.target.value)}
          disabled={isLoading}
          rows={10}
          placeholder={`Senior Backend Engineer, 5+ years Python, PostgreSQL, Docker required. Bangalore office, hybrid...\n\nPaste your full job description here — the more detail you provide, the better the matches.`}
          className="w-full resize-none text-[14px] text-[#1A1A1A] placeholder-[#A0A0A0] leading-relaxed outline-none rounded-lg p-4 border-2 border-[#E0E0E0] focus:border-[#2D7D3E] transition-colors bg-white disabled:opacity-60"
          style={{ background: "rgba(45,125,62,0.01)" }}
        />
        {charCount > 0 && (
          <p className={`text-[12px] mt-2 font-medium ${charCount < 50 ? "text-[#D4AF37]" : "text-[#2D7D3E]"}`}>
            {readiness}
          </p>
        )}
      </div>

      {/* Advanced settings */}
      <div className="border-t border-[#E0E0E0]">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between px-5 py-3 text-[13px] font-semibold text-[#4A4A4A] hover:text-[#2D7D3E] hover:bg-[#F5F5F5] transition-all"
        >
          <span>Advanced settings (optional)</span>
          <span className={`transition-transform duration-200 ${showAdvanced ? "rotate-180" : ""}`}>▼</span>
        </button>

        {showAdvanced && (
          <div className="px-5 pb-5 space-y-4 border-t border-[#E0E0E0] pt-4">
            {/* Top K */}
            <div>
              <div className="flex justify-between text-[13px] font-medium text-[#1A1A1A] mb-2">
                <span>Candidates to evaluate</span>
                <span className="text-[#2D7D3E] font-bold">{topK}</span>
              </div>
              <input type="range" min={3} max={15} value={topK} onChange={e => setTopK(Number(e.target.value))}
                className="w-full h-2 rounded-full appearance-none cursor-pointer bg-[#E0E0E0]"
                style={{ accentColor: "#2D7D3E" }}
              />
              <div className="flex justify-between text-[11px] text-[#A0A0A0] mt-1"><span>3</span><span>15</span></div>
            </div>

            {/* Match weight */}
            <div>
              <div className="flex justify-between text-[13px] font-medium text-[#1A1A1A] mb-2">
                <span>Match weight</span>
                <span className="text-[#2D7D3E] font-bold">{Math.round(matchWeight * 100)}% match / {Math.round((1 - matchWeight) * 100)}% interest</span>
              </div>
              <input type="range" min={0} max={100} value={Math.round(matchWeight * 100)} onChange={e => setMatchWeight(Number(e.target.value) / 100)}
                className="w-full h-2 rounded-full appearance-none cursor-pointer"
                style={{ accentColor: "#2D7D3E" }}
              />
            </div>

            {/* Turns */}
            <div>
              <div className="flex justify-between text-[13px] font-medium text-[#1A1A1A] mb-2">
                <span>Conversation turns per candidate</span>
                <span className="text-[#2D7D3E] font-bold">{turns}</span>
              </div>
              <input type="range" min={2} max={6} value={turns} onChange={e => setTurns(Number(e.target.value))}
                className="w-full h-2 rounded-full appearance-none cursor-pointer"
                style={{ accentColor: "#2D7D3E" }}
              />
              <div className="flex justify-between text-[11px] text-[#A0A0A0] mt-1"><span>Faster</span><span>More thorough</span></div>
            </div>
          </div>
        )}
      </div>

      {/* Scout button */}
      <div className="px-5 pb-5 pt-4">
        <button
          onClick={handleSubmit}
          disabled={!isReady}
          className={`w-full h-[48px] rounded-lg text-[15px] font-bold transition-all active:scale-[0.98] ${
            isReady
              ? "bg-[#2D7D3E] hover:bg-[#1F5A2B] text-white shadow-sm hover:shadow-md"
              : "bg-[#E0E0E0] text-[#A0A0A0] cursor-not-allowed"
          }`}
        >
          {isLoading ? "Scouting…" : "Scout candidates →"}
        </button>
        {!isLoading && charCount < 50 && charCount > 0 && (
          <p className="text-[12px] text-center text-[#A0A0A0] mt-2">Add at least 50 characters to continue</p>
        )}
      </div>
    </div>
  );
}
