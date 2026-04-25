"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { JDInput, ScoutFormData } from "@/components/JDInput";
import { ShortlistTable } from "@/components/ShortlistTable";
import { CandidateResult } from "@/components/CandidateCard";
import { ScoreSliders } from "@/components/ScoreSliders";
import { AlertCircle, CheckCircle2, Search } from "lucide-react";

interface ScoutResponseData {
  job_title: string | null;
  total_candidates_evaluated: number;
  shortlist: CandidateResult[];
  weights?: {
    match: number;
    interest: number;
  };
  [key: string]: unknown;
}

export default function Home() {
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<ScoutResponseData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);

  useEffect(() => {
    // Health check on load
    const checkHealth = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/health`, { method: "GET" });
        if (res.ok) {
          setIsBackendConnected(true);
        } else {
          setIsBackendConnected(false);
        }
      } catch {
        setIsBackendConnected(false);
      }
    };
    checkHealth();
  }, []);

  const handleScout = async (data: ScoutFormData) => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/scout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to fetch candidates");
      }

      const json = await res.json();
      setResults(json);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message || "An unexpected error occurred. Is the backend running?");
      } else {
        setError("An unexpected error occurred. Is the backend running?");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">
      {/* Top Bar */}
      <header className="h-[60px] border-b border-border bg-white dark:bg-[#1A1A1A] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-primary flex items-center justify-center">
            <Search className="w-4 h-4 text-white" />
          </div>
          <span className="text-[18px] font-semibold tracking-tight text-foreground">TalentRadar</span>
        </div>
        
        <div className="flex items-center gap-6">
          <nav className="hidden md:flex items-center gap-4">
            <button className="text-[14px] font-medium text-muted-foreground hover:text-foreground transition-colors">New Scout</button>
            <button className="text-[14px] font-medium text-muted-foreground hover:text-foreground transition-colors">Saved Results</button>
            <button className="text-[14px] font-medium text-muted-foreground hover:text-foreground transition-colors">Settings</button>
          </nav>
          
          <div className="flex items-center gap-2 text-[13px] font-medium bg-secondary px-3 py-1.5 rounded-full border border-border">
            {isBackendConnected === true ? (
              <>
                <span className="w-2 h-2 rounded-full bg-primary" />
                <span className="text-foreground">Connected</span>
              </>
            ) : isBackendConnected === false ? (
              <>
                <span className="w-2 h-2 rounded-full bg-destructive" />
                <span className="text-foreground">Offline</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                <span className="text-foreground">Checking...</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-[1200px] w-full mx-auto p-4 md:p-8 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Column: Input Form */}
        <div className={`transition-all duration-500 ease-out ${results || isLoading ? 'lg:col-span-4' : 'lg:col-span-8 lg:col-start-3'}`}>
          {!results && !isLoading && (
            <div className="mb-8 space-y-2">
              <h1 className="text-[28px] font-semibold text-foreground">Scout Candidates</h1>
              <p className="text-[14px] text-muted-foreground">
                Paste a job description below. Our AI will analyze the requirements, search the talent pool, and simulate screening conversations to find the best fit.
              </p>
            </div>
          )}
          
          <JDInput onSubmit={handleScout} isLoading={isLoading} />
          
          <AnimatePresence>
            {error && (
              <motion.div 
                initial={{ opacity: 0, height: 0, y: -10 }}
                animate={{ opacity: 1, height: "auto", y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-6 p-4 rounded-md bg-[rgba(211,47,47,0.1)] border-l-4 border-destructive text-foreground text-[14px] flex items-start gap-3"
              >
                <AlertCircle className="w-5 h-5 text-destructive shrink-0" />
                <span><strong>Error:</strong> {error}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right Column: Results or Empty State */}
        <div className={`transition-all duration-500 ease-out ${results || isLoading ? 'lg:col-span-8' : 'hidden'}`}>
          {isLoading && !results && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-card border border-border rounded-lg p-8 shadow-sm flex flex-col items-center justify-center min-h-[400px] text-center"
            >
              <div className="w-12 h-12 mb-6 relative">
                <div className="absolute inset-0 border-4 border-secondary rounded-full"></div>
                <div className="absolute inset-0 border-4 border-accent border-t-transparent rounded-full animate-spin"></div>
              </div>
              <h2 className="text-[20px] font-semibold text-foreground mb-2">Scouting candidates...</h2>
              <p className="text-[14px] text-muted-foreground max-w-sm mx-auto mb-8">
                This process takes about 2-3 minutes as we conduct deep conversational screening with top matches.
              </p>
              
              <div className="w-full max-w-sm text-left space-y-3">
                <div className="flex items-center gap-3 text-[14px]">
                  <CheckCircle2 className="w-5 h-5 text-primary" />
                  <span className="text-foreground">Parsing job description</span>
                </div>
                <div className="flex items-center gap-3 text-[14px]">
                  <CheckCircle2 className="w-5 h-5 text-primary" />
                  <span className="text-foreground">Searching candidate pool</span>
                </div>
                <div className="flex items-center gap-3 text-[14px]">
                  <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                  <span className="text-foreground font-medium">Running conversations & scoring...</span>
                </div>
              </div>
            </motion.div>
          )}

          {results && (
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-6"
            >
              <div className="mb-6 border-b border-border pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                  <h1 className="text-[28px] font-semibold text-foreground">
                    Results for {results.job_title || "the role"}
                  </h1>
                  <p className="text-[14px] text-muted-foreground mt-1">
                    {results.total_candidates_evaluated} candidates evaluated, {results.shortlist?.length || 0} ranked
                  </p>
                </div>
                {results.weights && (
                  <div className="text-[13px] text-muted-foreground bg-secondary px-3 py-1.5 rounded-md border border-border">
                    Current Weights: Match {Math.round(results.weights.match * 100)}% / Interest {Math.round(results.weights.interest * 100)}%
                  </div>
                )}
              </div>

              <ScoreSliders 
                initialMatchWeight={results.weights?.match ?? 0.6}
                shortlist={results.shortlist || []}
                onReRank={(newShortlist, newWeight) => {
                  setResults({
                    ...results,
                    shortlist: newShortlist,
                    weights: { match: newWeight, interest: 1 - newWeight }
                  });
                }}
              />
              
              <ShortlistTable candidates={results.shortlist || []} />
            </motion.div>
          )}
        </div>
      </main>
    </div>
  );
}
