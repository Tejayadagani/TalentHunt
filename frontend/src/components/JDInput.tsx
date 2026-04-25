"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";

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
  const [turns, setTurns] = useState(6);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (jdText.length < 50) return;
    
    onSubmit({
      jd_text: jdText,
      top_k: topK,
      match_weight: matchWeight,
      conversation_turns: turns,
    });
  };

  const isSubmitDisabled = jdText.length < 50 || isLoading;

  return (
    <div className="bg-card text-card-foreground border border-border rounded-lg p-5 shadow-sm">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="jd" className="block text-[14px] font-semibold text-[#1A1A1A] dark:text-white">
            Job description (paste raw text)
          </label>
          <Textarea
            id="jd"
            placeholder="Senior Backend Engineer, 5+ years Python, PostgreSQL, Docker required. Bangalore office, hybrid..."
            className="min-h-[200px] p-3 text-[14px] font-mono bg-white dark:bg-[#121212] border-[#E0E0E0] dark:border-[#333333] placeholder:text-[#4A4A4A] placeholder:italic focus-visible:ring-0 focus-visible:border-[#D4AF37] focus-visible:shadow-[0_0_0_3px_rgba(45,125,62,0.1)] transition-shadow resize-y"
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            disabled={isLoading}
          />
          <div className="flex justify-between text-[13px] text-muted-foreground uppercase tracking-wide font-medium">
            <span>{jdText.length} characters</span>
            {jdText.length > 0 && jdText.length < 50 && (
              <span className="text-destructive normal-case tracking-normal">Minimum 50 characters required</span>
            )}
          </div>
        </div>

        <div>
          <button
            type="button"
            className="flex items-center text-[14px] font-medium text-primary hover:underline bg-transparent border-none p-0 cursor-pointer"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <Settings2 className="w-4 h-4 mr-2" />
            {showAdvanced ? "Hide Advanced Settings" : "Show Advanced Settings"}
          </button>
        </div>

        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="p-4 rounded-md bg-secondary border border-border space-y-6 my-2">
                
                {/* Top K */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-[13px] font-medium text-muted-foreground uppercase tracking-wide">Candidates to Evaluate</label>
                    <span className="text-[14px] font-semibold text-foreground">{topK}</span>
                  </div>
                  <Slider
                    disabled={isLoading}
                    value={[topK]}
                    min={1}
                    max={15}
                    step={1}
                    onValueChange={(vals) => setTopK(typeof vals === "number" ? vals : vals[0])}
                    className="[&_[role=slider]]:bg-primary [&_[role=slider]]:border-primary"
                  />
                </div>

                {/* Match Weight */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-[13px] font-medium text-muted-foreground uppercase tracking-wide">Match Score Weight</label>
                    <span className="text-[14px] font-semibold text-foreground">{Math.round(matchWeight * 100)}% Match</span>
                  </div>
                  <Slider
                    disabled={isLoading}
                    value={[matchWeight]}
                    min={0}
                    max={1}
                    step={0.1}
                    onValueChange={(vals) => setMatchWeight(typeof vals === "number" ? vals : vals[0])}
                    className="[&_[role=slider]]:bg-primary [&_[role=slider]]:border-primary"
                  />
                  <div className="flex justify-between text-[13px] text-muted-foreground">
                    <span>0%</span>
                    <span>100%</span>
                  </div>
                </div>

                {/* Conversation Turns */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-[13px] font-medium text-muted-foreground uppercase tracking-wide">Simulation Turns</label>
                    <span className="text-[14px] font-semibold text-foreground">{turns}</span>
                  </div>
                  <Slider
                    disabled={isLoading}
                    value={[turns]}
                    min={2}
                    max={10}
                    step={1}
                    onValueChange={(vals) => setTurns(typeof vals === "number" ? vals : vals[0])}
                    className="[&_[role=slider]]:bg-primary [&_[role=slider]]:border-primary"
                  />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          whileTap={isSubmitDisabled ? {} : { scale: 0.98 }}
          type="submit"
          disabled={isSubmitDisabled}
          className={`w-full h-[44px] rounded-[6px] text-white text-[14px] font-semibold flex items-center justify-center transition-colors ${
            isSubmitDisabled
              ? "bg-[#E0E0E0] text-[#A0A0A0] cursor-not-allowed dark:bg-[#333333] dark:text-[#777777]"
              : "bg-[#2D7D3E] hover:bg-[#1F5A2B] shadow-[0_2px_4px_rgba(0,0,0,0.1)] active:shadow-inner"
          }`}
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Scouting candidates...
            </span>
          ) : (
            "Scout Candidates"
          )}
        </motion.button>
      </form>
    </div>
  );
}
