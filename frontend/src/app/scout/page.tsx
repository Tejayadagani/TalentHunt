"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { JDInput, ScoutFormData } from "@/components/JDInput";
import { ShortlistTable } from "@/components/ShortlistTable";
import { CandidateResult } from "@/components/CandidateCard";
import { ScoreSliders } from "@/components/ScoreSliders";
import { SavedResultsModal, SavedScout } from "@/components/SavedResultsModal";
import { SettingsModal } from "@/components/SettingsModal";
import { AlertCircle, Search, Bookmark, BookmarkCheck, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface ScoutResponseData {
  job_title: string | null;
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

// ── Loading State ─────────────────────────────────────────
function LoadingState() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const remaining = Math.max(0, 150 - elapsed);
  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border border-[#E0E0E0] rounded-xl p-10 shadow-sm flex flex-col items-center justify-center min-h-[480px] text-center"
    >
      <div className="spinner-gold mb-8" />
      <h2 className="text-[22px] font-bold text-[#2D7D3E] mb-2">Scouting your candidates…</h2>
      <p className="text-[14px] text-[#4A4A4A] max-w-sm mx-auto mb-10 leading-relaxed">
        This typically takes 2–3 minutes as we conduct thoughtful screening conversations with each top match.
      </p>

      <div className="w-full max-w-xs text-left space-y-4 mb-8">
        {[
          { label: "Parsing your job description", done: true },
          { label: "Searching our talent pool", done: true },
          { label: "Running conversations & scoring", done: false, active: true },
          { label: "Generating explanations", done: false, active: false },
        ].map((step, i) => (
          <div key={i} className="flex items-center gap-3 text-[14px]">
            {step.done ? (
              <div className="w-6 h-6 rounded-full bg-[#2D7D3E] flex items-center justify-center shrink-0">
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 12 12">
                  <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            ) : step.active ? (
              <div className="w-6 h-6 rounded-full border-2 border-[#D4AF37] border-t-transparent animate-spin shrink-0" />
            ) : (
              <div className="w-6 h-6 rounded-full border-2 border-[#E0E0E0] shrink-0" />
            )}
            <span className={step.active ? "font-semibold text-[#1A1A1A]" : step.done ? "text-[#2D7D3E]" : "text-[#4A4A4A]"}>
              {step.label}
            </span>
          </div>
        ))}
      </div>

      <p className="text-[13px] italic text-[#4A4A4A]">
        Estimated time: ~{mins > 0 ? `${mins}m ` : ""}{secs}s remaining
      </p>
    </motion.div>
  );
}

// ── Main Page ─────────────────────────────────────────────
export default function ScoutPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<ScoutResponseData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  const [savedScouts, setSavedScouts] = useState<SavedScout[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

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
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      if (!apiUrl) throw new Error("NEXT_PUBLIC_API_URL is not defined.");
      const res = await fetch(`${apiUrl}/api/scout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Failed to fetch candidates");
      }
      setResults(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
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

  return (
    <div className="min-h-screen bg-[#F5F5F5] text-[#1A1A1A] flex flex-col font-sans">
      {/* Modals */}
      <SavedResultsModal isOpen={showSaved} onClose={() => setShowSaved(false)} savedScouts={savedScouts} onLoad={handleLoadScout} onDelete={handleDeleteScout} />
      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />

      {/* ── Header ── */}
      <header className="h-16 bg-white border-b border-[#E0E0E0] px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-1 text-[13px] text-[#4A4A4A] hover:text-[#2D7D3E] transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
          <div className="w-px h-5 bg-[#E0E0E0]" />
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-[#2D7D3E] flex items-center justify-center">
              <Search className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-[17px] font-bold text-[#1A1A1A]">TalentRadar</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <nav className="hidden md:flex items-center gap-1">
            <button onClick={() => { setResults(null); setError(null); setIsSaved(false); }}
              className="text-[13px] font-medium text-[#4A4A4A] hover:text-[#2D7D3E] hover:bg-[#E8F5E9] px-3 py-2 rounded-md transition-all">
              Start new search
            </button>
            <button onClick={() => setShowSaved(true)}
              className="flex items-center gap-1.5 text-[13px] font-medium text-[#4A4A4A] hover:text-[#2D7D3E] hover:bg-[#E8F5E9] px-3 py-2 rounded-md transition-all">
              Saved results
              {savedScouts.length > 0 && (
                <span className="text-[10px] bg-[#2D7D3E] text-white rounded-full w-4 h-4 flex items-center justify-center font-bold">
                  {savedScouts.length}
                </span>
              )}
            </button>
            <button onClick={() => setShowSettings(true)}
              className="text-[13px] font-medium text-[#4A4A4A] hover:text-[#2D7D3E] hover:bg-[#E8F5E9] px-3 py-2 rounded-md transition-all">
              How it works
            </button>
          </nav>

          <div className={`flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1.5 rounded-full border ${
            isBackendConnected === true ? "bg-[#E8F5E9] border-[#2D7D3E]/20 text-[#2D7D3E]"
            : isBackendConnected === false ? "bg-red-50 border-red-200 text-red-600"
            : "bg-[#F5F5F5] border-[#E0E0E0] text-[#4A4A4A]"
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
              <h1 className="text-[26px] font-bold text-[#1A1A1A] mb-1">Scout candidates</h1>
              <p className="text-[14px] text-[#4A4A4A] leading-relaxed">
                Paste a job description below. Our AI will analyse the requirements, search the talent pool, and simulate screening conversations to find the best match.
              </p>
            </div>
          )}
          <JDInput onSubmit={handleScout} isLoading={isLoading} />
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 p-4 rounded-lg bg-red-50 border-l-4 border-red-500 text-[14px] flex items-start gap-3"
              >
                <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                <span className="text-[#1A1A1A]"><strong>Error:</strong> {error}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right: Results */}
        <div className={`transition-all duration-500 ease-out ${results || isLoading ? "lg:col-span-8" : "hidden"}`}>
          {isLoading && !results && <LoadingState />}

          {results && (
            <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} className="space-y-5">
              {/* Results header */}
              <div className="bg-white border border-[#E0E0E0] rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm">
                <div>
                  <h2 className="text-[22px] font-bold text-[#1A1A1A]">
                    Results for {results.job_title || "your role"}
                  </h2>
                  <p className="text-[13px] text-[#4A4A4A] mt-0.5">
                    {results.total_candidates_evaluated} candidates evaluated · {results.shortlist?.length || 0} ranked
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {/* Summary pill */}
                  <div className="hidden md:block bg-[#E8F5E9] border-l-4 border-[#2D7D3E] px-4 py-2 rounded-r-md">
                    <p className="text-[12px] font-semibold text-[#2D7D3E]">Ready to move forward?</p>
                    <p className="text-[11px] text-[#4A4A4A]">Here are your top matches.</p>
                  </div>
                  <button
                    onClick={handleSaveResult}
                    disabled={isSaved}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold border transition-all ${
                      isSaved ? "bg-[#E8F5E9] text-[#2D7D3E] border-[#2D7D3E]/30 cursor-default"
                        : "border-[#E0E0E0] text-[#4A4A4A] hover:text-[#2D7D3E] hover:border-[#2D7D3E] hover:bg-[#E8F5E9]"
                    }`}
                  >
                    {isSaved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                    {isSaved ? "Saved" : "Save result"}
                  </button>
                </div>
              </div>

              <ScoreSliders
                initialMatchWeight={results.weights?.match ?? 0.6}
                shortlist={results.shortlist || []}
                onReRank={(newShortlist, newWeight) => setResults({ ...results, shortlist: newShortlist, weights: { match: newWeight, interest: 1 - newWeight } })}
              />

              <ShortlistTable candidates={results.shortlist || []} />
            </motion.div>
          )}
        </div>
      </main>
    </div>
  );
}
