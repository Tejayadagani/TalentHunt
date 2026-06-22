"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { JDInput, ScoutFormData } from "@/components/JDInput";
import { ShortlistTable } from "@/components/ShortlistTable";
import { CandidateResult } from "@/components/CandidateCard";
import { ScoreSliders } from "@/components/ScoreSliders";
import { SavedResultsModal, SavedScout } from "@/components/SavedResultsModal";
import { SettingsModal } from "@/components/SettingsModal";
import { AlertCircle, Search, Bookmark, BookmarkCheck, ArrowLeft, Download, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import ShapeGrid from "@/components/ShapeGrid";
import { AgentPipeline } from "@/components/AgentPipeline";

interface ScoutResponseData {
  job_title: string | null;
  parsed_jd?: any;
  total_candidates_evaluated: number;
  shortlist: CandidateResult[];
  weights?: { match: number; interest: number };
  [key: string]: unknown;
}

const STORAGE_KEY = "talentradar_saved_scouts";

function loadSavedScouts(): SavedScout[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
function persistScouts(scouts: SavedScout[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(scouts));
}

// ── Main Page ─────────────────────────────────────────────
export default function ScoutPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [activeAgent, setActiveAgent] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const [results, setResults] = useState<ScoutResponseData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  const [savedScouts, setSavedScouts] = useState<SavedScout[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [modelSwapToast, setModelSwapToast] = useState<string | null>(null);
  const [currentTurns, setCurrentTurns] = useState(6);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const router = useRouter();

  // Auto-hide model swap toast after 4s
  useEffect(() => {
    if (!modelSwapToast) return;
    const t = setTimeout(() => setModelSwapToast(null), 4000);
    return () => clearTimeout(t);
  }, [modelSwapToast]);

  useEffect(() => { setSavedScouts(loadSavedScouts()); }, []);

  useEffect(() => {
    const check = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL;
        if (!apiUrl) throw new Error("missing url");
        const res = await fetch(`${apiUrl}/api/health`);
        setIsBackendConnected(res.ok);
      } catch { setIsBackendConnected(false); }
    };
    check();
  }, []);

  const handleScout = async (data: ScoutFormData) => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    setIsSaved(false);
    setActiveAgent(1);
    setCompletedCount(0);
    setTotalCandidates(100);
    setCurrentTurns(data.conversation_turns);
    setLoadingMessage("Parsing JD and searching talent pool (Fast Mode)...");
    
    try {
      let apiUrl = process.env.NEXT_PUBLIC_API_URL;
      if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not defined.");
      apiUrl = apiUrl.replace(/\/+$/, ""); // Remove trailing slashes
      
      const res = await fetch(`${apiUrl}/api/scout/fast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Failed to scout candidates");
      }

      setActiveAgent(2);
      const resultData = await res.json();
      setResults(resultData);
      setCompletedCount(resultData.shortlist?.length || 0);
      setActiveAgent(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoScout = async () => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    setIsSaved(false);
    setActiveAgent(0);
    setCompletedCount(100);
    setTotalCandidates(100);
    setLoadingMessage("Loading precomputed offline results...");

    try {
      let apiUrl = process.env.NEXT_PUBLIC_API_URL;
      if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not defined.");
      apiUrl = apiUrl.replace(/\/+$/, "");

      const res = await fetch(`${apiUrl}/api/demo`);
      if (!res.ok) {
        throw new Error("Failed to load demo results");
      }
      const data = await res.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleStartBulkInterviews = () => {
    if (!results || !results.parsed_jd || selectedIds.size === 0) return;
    
    // Get the full candidate objects for the selected IDs
    const selectedCandidates = results.shortlist.filter((c, idx) => {
      const cid = c.id || (c as any).candidate_id || String(idx);
      return selectedIds.has(cid);
    });
    
    // Save to localStorage so the /interviews page can pick it up
    localStorage.setItem("talentradar_pending_interviews", JSON.stringify({
      candidates: selectedCandidates,
      parsed_jd: results.parsed_jd,
      weights: results.weights || { match: 0.6, interest: 0.4 },
      conversation_turns: currentTurns,
      job_title: results.job_title
    }));
    
    // Redirect to the dedicated interviews page
    router.push("/interviews");
  };

  const handleSaveResult = () => {
    if (!results) return;
    const scout: SavedScout = {
      id: `scout_${Date.now()}`,
      timestamp: Date.now(),
      job_title: results.job_title || "Untitled Role",
      results,
    };
    const updated = [scout, ...savedScouts];
    setSavedScouts(updated);
    persistScouts(updated);
    setIsSaved(true);
  };

  const handleDeleteScout = (id: string) => {
    const updated = savedScouts.filter(s => s.id !== id);
    setSavedScouts(updated);
    persistScouts(updated);
  };

  const handleLoadScout = (loadedResults: Record<string, unknown>) => {
    setResults(loadedResults as ScoutResponseData);
    setShowSaved(false);
    setIsSaved(true);
  };

  const handleExportCSV = () => {
    if (!results?.shortlist?.length) return;
    const rows = results.shortlist.map((c: any, i) => ({
      candidate_id: c.id || c.candidate_id || "Unknown_ID",
      rank: i + 1,
      score: (c.combined_score / 100).toFixed(4),
      reasoning: c.explanation || c.match_reason || "",
    }));
    const header = "candidate_id,rank,score,reasoning";
    const body = rows.map(r =>
      `${r.candidate_id},${r.rank},${r.score},"${String(r.reasoning).replace(/"/g, "'")}"`
    ).join("\n");
    const csv = `${header}\n${body}`;
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `submission_${results.job_title?.replace(/\s+/g, "_") || "talentradar"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white flex flex-col font-sans relative overflow-hidden">
      <ShapeGrid className="absolute inset-0 z-0 opacity-30" hoverTrailAmount={5} shape="hexagon" speed={0.5} squareSize={40} borderColor="#1F5A2B" hoverFillColor="#2D7D3E" />

      {/* ── Model swap toast ── */}
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
      {/* Modals */}
      <SavedResultsModal isOpen={showSaved} onClose={() => setShowSaved(false)} savedScouts={savedScouts} onLoad={handleLoadScout} onDelete={handleDeleteScout} />
      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />

      {/* ── Header ── */}
      <header className="h-16 bg-[#0A0A0A]/80 backdrop-blur-xl border-b border-[#333] px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-1 text-[13px] text-[#A0A0A0] hover:text-[#4A9D5F] transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Home
          </a>
          <div className="w-px h-5 bg-[#333]" />
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-[#2D7D3E] flex items-center justify-center shadow-lg shadow-[#2D7D3E]/20">
              <Search className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-[17px] font-bold text-white">TalentRadar</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <nav className="hidden md:flex items-center gap-1">
            <button onClick={() => { setResults(null); setError(null); setIsSaved(false); }}
              className="text-[13px] font-medium text-[#A0A0A0] hover:text-white hover:bg-[#1A1A1A] px-3 py-2 rounded-md transition-all">
              Start new search
            </button>
            <button onClick={() => setShowSaved(true)}
              className="flex items-center gap-1.5 text-[13px] font-medium text-[#A0A0A0] hover:text-white hover:bg-[#1A1A1A] px-3 py-2 rounded-md transition-all">
              Saved results
              {savedScouts.length > 0 && (
                <span className="text-[10px] bg-[#2D7D3E] text-white rounded-full w-4 h-4 flex items-center justify-center font-bold">
                  {savedScouts.length}
                </span>
              )}
            </button>
            <button onClick={() => setShowSettings(true)}
              className="text-[13px] font-medium text-[#A0A0A0] hover:text-white hover:bg-[#1A1A1A] px-3 py-2 rounded-md transition-all">
              How it works
            </button>
          </nav>

          <div className={`flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1.5 rounded-full border ${
            isBackendConnected === true ? "bg-[#1A3A22]/50 border-[#2D7D3E]/30 text-[#4A9D5F]"
            : isBackendConnected === false ? "bg-red-900/30 border-red-500/30 text-red-400"
            : "bg-[#1A1A1A]/50 border-[#333] text-[#A0A0A0]"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              isBackendConnected === true ? "bg-[#2D7D3E]"
              : isBackendConnected === false ? "bg-red-500"
              : "bg-[#4A4A4A] animate-pulse"
            }`} />
            {isBackendConnected === true ? "Connected" : isBackendConnected === false ? "Offline" : "Checking…"}
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 max-w-[1280px] w-full mx-auto p-4 md:p-8 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

        {/* Left: Input */}
        <div className={`transition-all duration-500 ease-out ${results || isLoading ? "lg:col-span-4" : "lg:col-span-7 lg:col-start-3"}`}>
          {!results && !isLoading && (
            <div className="mb-6">
              <h1 className="text-[26px] font-bold text-white mb-1">Scout candidates</h1>
              <p className="text-[14px] text-[#A0A0A0] leading-relaxed">
                Paste a job description below. Our AI will analyse the requirements, search the talent pool, and simulate screening conversations to find the best match.
              </p>
            </div>
          )}
          <JDInput onSubmit={handleScout} isLoading={isLoading} onDemoSubmit={handleDemoScout} />
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 p-4 rounded-lg bg-red-900/20 border-l-4 border-red-500 text-[14px] flex items-start gap-3 backdrop-blur-md"
              >
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <span className="text-white"><strong>Error:</strong> {error}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right: Results / Pipeline */}
        <div className={`transition-all duration-500 ease-out ${results || isLoading ? "lg:col-span-8" : "hidden"}`}>
          {isLoading && (
            <div className="mb-6">
              <AgentPipeline
                activeAgent={activeAgent}
                completedCount={completedCount}
                totalCandidates={totalCandidates}
                message={loadingMessage}
              />
            </div>
          )}

          {results && (
            <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} className="space-y-5">
              {/* Sticky Bulk Action Bar (if items selected) */}
              <AnimatePresence>
                {selectedIds.size > 0 && (
                  <motion.div 
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    className="sticky top-[80px] z-20 flex items-center justify-between bg-[#1A3A22]/90 border border-[#2D7D3E] backdrop-blur-xl rounded-xl p-4 shadow-2xl"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-[#2D7D3E] text-white flex items-center justify-center font-bold text-sm shadow-sm">
                        {selectedIds.size}
                      </div>
                      <div>
                        <p className="text-[14px] font-bold text-[#4A9D5F]">Candidates selected</p>
                        <p className="text-[12px] text-white/70">Ready to simulate interviews</p>
                      </div>
                    </div>
                    <button
                      onClick={handleStartBulkInterviews}
                      className="h-10 px-6 rounded-lg bg-[#2D7D3E] hover:bg-[#1F5A2B] text-white font-bold text-[14px] transition-all active:scale-[0.97] flex items-center gap-2 shadow-lg shadow-[#2D7D3E]/30"
                    >
                      Start Interviews
                      <ArrowLeft className="w-4 h-4 rotate-180" />
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
              {/* Results header */}
              <div className="bg-[#1A1A1A]/60 backdrop-blur-xl border border-[#333] rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg">
                <div>
                  <h2 className="text-[22px] font-bold text-white">
                    Results for {results.job_title || "your role"}
                  </h2>
                  <p className="text-[13px] text-[#A0A0A0] mt-0.5">
                    {results.total_candidates_evaluated} candidates evaluated · {results.shortlist?.length || 0} ranked
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {/* Summary pill */}
                  <div className="hidden md:block bg-[#1A3A22]/30 border-l-4 border-[#2D7D3E] px-4 py-2 rounded-r-md">
                    <p className="text-[12px] font-semibold text-[#4A9D5F]">Ready to move forward?</p>
                    <p className="text-[11px] text-[#A0A0A0]">Here are your top matches.</p>
                  </div>
                  <button
                    onClick={handleSaveResult}
                    disabled={isSaved}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold border transition-all ${
                      isSaved ? "bg-[#1A3A22]/50 text-[#4A9D5F] border-[#2D7D3E]/30 cursor-default"
                        : "border-[#333] text-[#A0A0A0] hover:text-white hover:border-[#4A9D5F] hover:bg-[#1A3A22]/30"
                    }`}
                  >
                    {isSaved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                    {isSaved ? "Saved" : "Save result"}
                  </button>
                  <button
                    onClick={handleExportCSV}
                    disabled={!results?.shortlist?.length}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold border border-[#333] text-[#A0A0A0] hover:text-white hover:border-[#D4AF37] hover:bg-[#2A1F00]/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    title="Download submission.csv"
                  >
                    <Download className="w-4 h-4" />
                    Download CSV
                  </button>
                </div>
              </div>

              <ScoreSliders
                initialMatchWeight={results.weights?.match ?? 0.6}
                shortlist={results.shortlist || []}
                onReRank={(newShortlist, newWeight) => setResults({ ...results, shortlist: newShortlist, weights: { match: newWeight, interest: 1 - newWeight } })}
              />

              <ShortlistTable 
                candidates={results.shortlist || []} 
                isLoading={isLoading} 
                selectedIds={selectedIds}
                onToggleSelect={handleToggleSelect}
                hideInterviewButton={true}
              />
            </motion.div>
          )}
        </div>
      </main>
      </div>
    </div>
  );
}
