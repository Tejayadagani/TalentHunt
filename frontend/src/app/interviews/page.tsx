"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { AgentPipeline } from "@/components/AgentPipeline";
import { ShortlistTable } from "@/components/ShortlistTable";
import ShapeGrid from "@/components/ShapeGrid";
import { AlertCircle, ArrowLeft, Zap, CheckCircle } from "lucide-react";
import { CandidateResult } from "@/components/CandidateCard";

export default function InterviewsPage() {
  const router = useRouter();
  const [isLoaded, setIsLoaded] = useState(false);
  const [candidates, setCandidates] = useState<CandidateResult[]>([]);
  const [parsedJd, setParsedJd] = useState<any>(null);
  const [weights, setWeights] = useState({ match: 0.6, interest: 0.4 });
  const [turns, setTurns] = useState(6);
  const [jobTitle, setJobTitle] = useState("");
  
  const [activeAgent, setActiveAgent] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [loadingMessage, setLoadingMessage] = useState("Ready to start interviews...");
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [modelSwapToast, setModelSwapToast] = useState<string | null>(null);

  // Auto-hide model swap toast
  useEffect(() => {
    if (!modelSwapToast) return;
    const t = setTimeout(() => setModelSwapToast(null), 4000);
    return () => clearTimeout(t);
  }, [modelSwapToast]);

  // Load state from local storage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem("skillsync_pending_interviews");
      if (raw) {
        const data = JSON.parse(raw);
        setCandidates(data.candidates || []);
        setParsedJd(data.parsed_jd);
        setWeights(data.weights);
        setTurns(data.conversation_turns || 6);
        setJobTitle(data.job_title || "Unknown Role");
        setIsLoaded(true);
      } else {
        router.push("/scout");
      }
    } catch (e) {
      router.push("/scout");
    }
  }, [router]);

  const hasStartedRef = useRef(false);

  // Start the sequential processing once loaded
  useEffect(() => {
    if (isLoaded && !isProcessing && !allDone && candidates.length > 0) {
      if (hasStartedRef.current) return;
      hasStartedRef.current = true;
      processInterviews();
    }
  }, [isLoaded]);

  const processInterviews = async () => {
    setIsProcessing(true);
    let currentCompleted = 0;

    for (let i = 0; i < candidates.length; i++) {
      const candidate = candidates[i];
      
      // Skip if already has transcript
      if (candidate.conversation_transcript && candidate.conversation_transcript.length > 0) {
        currentCompleted++;
        setCompletedCount(currentCompleted);
        continue;
      }

      try {
        setActiveAgent(3);
        setLoadingMessage(`Starting interview for ${candidate.name}...`);
        
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/interview/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate,
            parsed_jd: parsedJd,
            match_weight: weights.match,
            conversation_turns: turns,
          }),
        });

        if (!res.ok) {
          throw new Error("Failed to start interview");
        }

        if (!res.body) throw new Error("ReadableStream not supported");

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let done = false;
        let buffer = "";

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (value) {
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
              if (part.startsWith("data: ")) {
                try {
                  const event = JSON.parse(part.substring(6));
                  if (event.type === "info") {
                    setLoadingMessage(event.message);
                    if (event.agent) setActiveAgent(event.agent);
                  } else if (event.type === "candidate") {
                    // Update this candidate in the state
                    setCandidates(prev => prev.map(c => {
                      const cid1 = c.id || (c as any).candidate_id;
                      const cid2 = candidate.id || (candidate as any).candidate_id;
                      return cid1 === cid2 ? { ...c, ...event.data } : c;
                    }));
                    setActiveAgent(5); // Interest Scorer
                  } else if (event.type === "model_swap") {
                    setModelSwapToast(`⚡ ${event.from?.split("/").pop()} → ${event.to?.split("/").pop()}`);
                  } else if (event.type === "error") {
                    console.error("Error from stream:", event.message);
                  }
                } catch (e) {
                  // ignore parse error
                }
              }
            }
          }
        }
        
      } catch (err) {
        console.error("Failed interviewing candidate:", candidate.name, err);
      }
      
      currentCompleted++;
      setCompletedCount(currentCompleted);
    }

    setActiveAgent(6);
    setLoadingMessage("All interviews completed! Review the final scores below.");
    setAllDone(true);
    setIsProcessing(false);
  };

  if (!isLoaded) return null;

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex flex-col font-sans relative overflow-hidden">
      <ShapeGrid className="absolute inset-0 z-0 opacity-30" hoverTrailAmount={5} shape="hexagon" speed={0.5} squareSize={40} borderColor="#1F5A2B" hoverFillColor="#2D7D3E" />

      {modelSwapToast && (
        <div
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-semibold shadow-2xl"
          style={{ background: "rgba(212,175,55,0.15)", border: "1px solid rgba(212,175,55,0.4)", color: "#D4AF37", backdropFilter: "blur(12px)" }}
        >
          <Zap className="w-4 h-4" />
          {modelSwapToast}
        </div>
      )}

      <div className="relative z-10 flex flex-col min-h-screen">
        <header className="h-16 bg-[#0A0A0A]/80 backdrop-blur-xl border-b border-[#333] px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
          <div className="flex items-center gap-4">
            <button onClick={() => router.push("/scout")} className="flex items-center gap-1 text-[13px] text-[#A0A0A0] hover:text-[#4A9D5F] transition-colors">
              <ArrowLeft className="w-4 h-4" />
              Back to Scout
            </button>
            <div className="w-px h-5 bg-[#333]" />
            <h1 className="text-[17px] font-bold text-white">Interviewing Candidates</h1>
          </div>
        </header>

        <main className="flex-1 max-w-[800px] w-full mx-auto p-4 md:p-8 flex flex-col gap-8">
          
          {/* Permanent n8n Agent Pipeline */}
          <div className="w-full">
            <AgentPipeline
              activeAgent={activeAgent}
              completedCount={completedCount}
              totalCandidates={candidates.length}
              message={loadingMessage}
            />
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="p-4 rounded-lg bg-red-900/20 border-l-4 border-red-500 text-[14px] flex items-start gap-3 backdrop-blur-md"
              >
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <span className="text-white"><strong>Error:</strong> {error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="space-y-4">
            <h2 className="text-[20px] font-bold text-white mb-2">
              Selected Candidates for {jobTitle}
            </h2>
            
            {allDone && (
              <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="bg-[#1A3A22]/50 border border-[#2D7D3E]/50 rounded-xl p-6 text-center shadow-lg mb-6">
                <CheckCircle className="w-12 h-12 text-[#4A9D5F] mx-auto mb-3" />
                <h2 className="text-[22px] font-bold text-white">Interviews Successfully Completed</h2>
                <p className="text-[14px] text-[#A0A0A0] mt-1">Final scores have been generated. You can now review transcripts and send offer letters.</p>
              </motion.div>
            )}

            <ShortlistTable 
              candidates={candidates} 
              isLoading={false} 
              hideInterviewButton={true}
            />
          </div>

        </main>
      </div>
    </div>
  );
}
