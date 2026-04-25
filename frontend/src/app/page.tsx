"use client";

import Link from "next/link";
import { Search, ArrowRight, CheckCircle2, ChevronRight } from "lucide-react";

const STEPS = [
  {
    n: "01",
    title: "Paste your job description",
    desc: "Drop in raw text — any length, any format. Our parser extracts skills, seniority, location, budget, and domain automatically.",
  },
  {
    n: "02",
    title: "We scout and screen",
    desc: "TalentRadar searches the talent pool by semantic similarity, then simulates a real screening conversation with each top match.",
  },
  {
    n: "03",
    title: "Review your shortlist",
    desc: "Get a ranked list with Match Score, Interest Score, and the full conversation transcript behind every decision. No black box.",
  },
];

const WHY = [
  {
    title: "Skill match + genuine interest",
    desc: "Most tools just match keywords. TalentRadar also measures whether candidates will actually accept the offer — before you pick up the phone.",
  },
  {
    title: "Fully transparent scoring",
    desc: "Every score is backed by a real simulated conversation you can read. You know exactly why Rank #1 is Rank #1.",
  },
  {
    title: "Ready to move fast",
    desc: "Top candidates ranked with salary expectations, notice period, and location — everything you need to make the call today.",
  },
];

const SAMPLE = {
  name: "Priya Nair",
  title: "Senior Software Engineer",
  company: "Razorpay",
  years: 5,
  location: "Bangalore",
  match: 88,
  interest: 86,
  combined: 87,
  explanation:
    "Priya demonstrated high enthusiasm and asked thoughtful questions about team structure and tech stack. Her fintech background maps directly to the role. Salary expectation ₹28L is within budget. Available in 45 days.",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#FFFFFF] text-[#1A1A1A] font-sans">

      {/* ── NAV ── */}
      <header className="sticky top-0 z-40 bg-white border-b border-[#E0E0E0] px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-[#2D7D3E] flex items-center justify-center">
            <Search className="w-4 h-4 text-white" />
          </div>
          <span className="text-[20px] font-bold text-[#1A1A1A]">TalentRadar</span>
        </div>
        <nav className="hidden md:flex items-center gap-6">
          <a href="#how-it-works" className="text-[14px] text-[#4A4A4A] hover:text-[#2D7D3E] transition-colors">How it works</a>
          <a href="#why" className="text-[14px] text-[#4A4A4A] hover:text-[#2D7D3E] transition-colors">Why TalentRadar</a>
        </nav>
        <Link
          href="/scout"
          className="bg-[#2D7D3E] hover:bg-[#1F5A2B] text-white text-[14px] font-semibold px-5 py-2.5 rounded-md transition-colors"
        >
          Get started
        </Link>
      </header>

      {/* ── HERO ── */}
      <section
        className="relative px-6 py-24 md:py-36"
        style={{ background: "linear-gradient(135deg, #2D7D3E 0%, #1F5A2B 100%)" }}
      >
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-white text-[13px] font-medium mb-8">
            <span className="w-2 h-2 rounded-full bg-[#D4AF37]" />
            Built for Catalyst 2026 — AI Recruitment Track
          </div>
          <h1 className="text-[48px] md:text-[56px] font-bold text-white leading-[1.15] mb-6">
            Find your next hire in minutes,<br className="hidden md:block" /> not days.
          </h1>
          <p className="text-[18px] text-[#E8E8E8] leading-relaxed max-w-2xl mx-auto mb-10">
            Stop wasting time sifting through resumes. TalentRadar scouts candidates based on skills <em>and</em> genuine interest — then gives you a ranked shortlist with transparent scoring you can trust.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/scout"
              className="flex items-center gap-2 bg-[#D4AF37] hover:bg-[#B8941F] text-[#1A1A1A] font-bold text-[16px] px-8 py-4 rounded-md shadow-lg transition-all hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
            >
              Start scouting
              <ArrowRight className="w-5 h-5" />
            </Link>
            <a
              href="#how-it-works"
              className="text-white/80 hover:text-white text-[15px] font-medium underline underline-offset-4 transition-colors"
            >
              See how it works ↓
            </a>
          </div>
        </div>
        {/* Decorative bottom fade */}
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-b from-transparent to-white pointer-events-none" />
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="how-it-works" className="px-6 py-20 max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-[32px] font-bold text-[#1A1A1A] mb-3">How it works</h2>
          <p className="text-[16px] text-[#4A4A4A]">Three steps from job description to ranked shortlist.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {STEPS.map((step, i) => (
            <div
              key={i}
              className="bg-white border border-[#E0E0E0] rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow"
              style={{ borderLeft: "4px solid #2D7D3E" }}
            >
              <div className="text-[28px] font-bold text-[#2D7D3E] mb-3">{step.n}</div>
              <h3 className="text-[16px] font-bold text-[#1A1A1A] mb-2">{step.title}</h3>
              <p className="text-[14px] text-[#4A4A4A] leading-relaxed">{step.desc}</p>
              {i < 2 && (
                <div className="hidden md:block absolute -right-4 top-1/2 -translate-y-1/2 z-10">
                  <ChevronRight className="w-6 h-6 text-[#2D7D3E]" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── WHY TALENTREADER ── */}
      <section
        id="why"
        className="px-6 py-16"
        style={{ background: "#F5F5F5" }}
      >
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-[32px] font-bold text-[#1A1A1A] mb-3">Why TalentRadar?</h2>
            <p className="text-[16px] text-[#4A4A4A]">Built to solve the real problems in technical hiring.</p>
          </div>
          <div
            className="bg-white rounded-xl overflow-hidden"
            style={{ border: "1px solid #E0E0E0", borderTop: "4px solid #D4AF37", borderBottom: "4px solid #D4AF37" }}
          >
            {WHY.map((item, i) => (
              <div key={i} className={`flex items-start gap-4 p-6 ${i < WHY.length - 1 ? "border-b border-[#E0E0E0]" : ""}`}>
                <div className="w-8 h-8 rounded-full bg-[#2D7D3E] flex items-center justify-center shrink-0 mt-0.5">
                  <CheckCircle2 className="w-4 h-4 text-white" />
                </div>
                <div>
                  <p className="text-[13px] font-bold text-[#2D7D3E] uppercase tracking-wide mb-1">{item.title}</p>
                  <p className="text-[14px] text-[#4A4A4A] leading-[1.7]">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SAMPLE OUTPUT ── */}
      <section className="px-6 py-20 max-w-4xl mx-auto">
        <div className="text-center mb-10">
          <h2 className="text-[32px] font-bold text-[#1A1A1A] mb-3">What the output looks like</h2>
          <p className="text-[16px] text-[#4A4A4A]">Real data, transparent reasoning, ready to act on.</p>
        </div>
        <div className="rounded-xl overflow-hidden" style={{ background: "#1A1A1A" }}>
          <div className="p-6 border-b border-[#333333]">
            <div className="flex items-center gap-3 mb-1">
              <span className="bg-[#2D7D3E] text-white text-[12px] font-bold px-2.5 py-1 rounded">Rank #1</span>
              <h3 className="text-[18px] font-bold text-white">{SAMPLE.name}</h3>
            </div>
            <p className="text-[13px] text-[#A0A0A0]">
              {SAMPLE.title} at {SAMPLE.company} · {SAMPLE.years} yrs · {SAMPLE.location}
            </p>
          </div>
          <div className="p-6 border-b border-[#333333]">
            <div className="flex gap-3 flex-wrap">
              <div className="bg-[#2D7D3E] px-4 py-2 rounded-lg text-center">
                <p className="text-[11px] text-white/70 uppercase tracking-wide font-bold">Match</p>
                <p className="text-[24px] font-bold text-white">{SAMPLE.match}</p>
              </div>
              <div className="bg-[#2D7D3E] px-4 py-2 rounded-lg text-center">
                <p className="text-[11px] text-white/70 uppercase tracking-wide font-bold">Interest</p>
                <p className="text-[24px] font-bold text-white">{SAMPLE.interest}</p>
              </div>
              <div className="px-4 py-2 rounded-lg text-center" style={{ background: "#D4AF37" }}>
                <p className="text-[11px] text-[#1A1A1A]/70 uppercase tracking-wide font-bold">Combined</p>
                <p className="text-[24px] font-bold text-[#1A1A1A]">{SAMPLE.combined}</p>
              </div>
            </div>
          </div>
          <div className="p-6 border-b border-[#333333]">
            <p
              className="text-[14px] text-[#A0A0A0] italic leading-relaxed pl-4"
              style={{ borderLeft: "2px solid #D4AF37" }}
            >
              &ldquo;{SAMPLE.explanation}&rdquo;
            </p>
          </div>
          <div className="p-6">
            <Link
              href="/scout"
              className="inline-flex items-center gap-2 border-2 border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37] hover:text-[#1A1A1A] font-semibold text-[14px] px-5 py-2.5 rounded-md transition-all"
            >
              See full results like this
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section
        className="px-6 py-20 text-center"
        style={{ background: "linear-gradient(180deg, #2D7D3E 0%, #1F5A2B 100%)" }}
      >
        <h2 className="text-[36px] font-bold text-white mb-4">Ready to find your next hire?</h2>
        <p className="text-[16px] text-[#E8E8E8] mb-8 max-w-xl mx-auto">
          Paste a job description and get a fully evaluated, ranked shortlist in under 3 minutes.
        </p>
        <Link
          href="/scout"
          className="inline-flex items-center gap-2 bg-[#D4AF37] hover:bg-[#B8941F] text-[#1A1A1A] font-bold text-[16px] px-10 py-4 rounded-md shadow-lg transition-all hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
        >
          Start scouting now
          <ArrowRight className="w-5 h-5" />
        </Link>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-[#1A1A1A] px-6 py-8">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-[#2D7D3E] flex items-center justify-center">
              <Search className="w-3 h-3 text-white" />
            </div>
            <span className="text-white font-bold text-[15px]">TalentRadar</span>
          </div>
          <p className="text-[13px] text-[#4A4A4A]">
            Built for Catalyst by Deccan AI · Powered by Groq Llama 3.3 & ChromaDB
          </p>
          <a
            href="https://github.com/Charan512/TalentHunt"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[13px] text-[#4A4A4A] hover:text-white transition-colors"
          >
            GitHub →
          </a>
        </div>
      </footer>
    </div>
  );
}
