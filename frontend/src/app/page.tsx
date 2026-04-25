"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, FileText, Radar, ListOrdered, Trophy } from "lucide-react";

// ── SVG Radar Logo ─────────────────────────────────────────
function RadarLogo({ size = 32, color = "#2D7D3E" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Outer ring */}
      <circle cx="16" cy="16" r="14" stroke={color} strokeWidth="1.5" opacity="0.3" />
      {/* Mid ring */}
      <circle cx="16" cy="16" r="9" stroke={color} strokeWidth="1.5" opacity="0.5" />
      {/* Inner ring */}
      <circle cx="16" cy="16" r="4.5" stroke={color} strokeWidth="1.5" opacity="0.8" />
      {/* Sweep line */}
      <line x1="16" y1="16" x2="28" y2="8" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      {/* Center dot - gold */}
      <circle cx="16" cy="16" r="2.5" fill="#D4AF37" />
      {/* Detected blip */}
      <circle cx="25" cy="10" r="2" fill={color} opacity="0.9" />
    </svg>
  );
}

// ── Animated Radar Ring Background ────────────────────────
function RadarAnimation() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
      <div className="relative" style={{ width: 600, height: 600, opacity: 0.12 }}>
        {[0, 1, 2, 3].map(i => (
          <div
            key={i}
            className="absolute inset-0 rounded-full border border-white"
            style={{
              transform: `scale(${0.25 + i * 0.25})`,
              animation: `pulse 4s ease-out ${i * 0.8}s infinite`,
            }}
          />
        ))}
        {/* Sweep */}
        <div
          className="absolute"
          style={{
            width: "50%",
            height: "2px",
            top: "50%",
            left: "50%",
            transformOrigin: "left center",
            background: "linear-gradient(to right, rgba(212,175,55,0.8), transparent)",
            animation: "sweep 6s linear infinite",
            borderRadius: 2,
          }}
        />
        <style>{`
          @keyframes sweep { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
          @keyframes pulse { 0%, 100% { opacity: 0.15; } 50% { opacity: 0.4; } }
        `}</style>
      </div>
    </div>
  );
}

// ── Floating candidate cards in hero ─────────────────────
function FloatingCard({ name, role, score, delay, x, y }: {
  name: string; role: string; score: number; delay: number; x: string; y: string;
}) {
  return (
    <div
      className="absolute hidden md:block"
      style={{
        left: x, top: y,
        animation: `float 6s ease-in-out ${delay}s infinite`,
      }}
    >
      <div className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl p-3 w-44 shadow-xl">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center">
            <span className="text-[10px] font-bold text-white">{name[0]}</span>
          </div>
          <div>
            <p className="text-[11px] font-bold text-white leading-tight">{name}</p>
            <p className="text-[9px] text-white/60 leading-tight">{role}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-white/20 overflow-hidden">
            <div className="h-full rounded-full bg-[#D4AF37]" style={{ width: `${score}%` }} />
          </div>
          <span className="text-[11px] font-bold text-[#D4AF37]">{score}</span>
        </div>
      </div>
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
      `}</style>
    </div>
  );
}

// ── Stats row ─────────────────────────────────────────────
const STATS = [
  { value: "5", label: "AI agents working in parallel" },
  { value: "< 3min", label: "Average time to shortlist" },
  { value: "100%", label: "Transparent scoring" },
  { value: "0", label: "Black boxes" },
];

// ── Steps ─────────────────────────────────────────────────
const STEPS: { n: string; title: string; desc: string; Icon: React.ElementType }[] = [
  {
    n: "01",
    title: "Paste your job description",
    desc: "Drop in raw text — any format, any length. Our parser extracts skills, seniority, location, budget, and domain automatically.",
    Icon: FileText,
  },
  {
    n: "02",
    title: "We scout and screen candidates",
    desc: "TalentRadar searches the talent pool by semantic similarity, then simulates a real screening conversation with each top match.",
    Icon: Radar,
  },
  {
    n: "03",
    title: "Review your ranked shortlist",
    desc: "Get a ranked list with Match Score, Interest Score, and the full conversation transcript behind every decision. No guessing.",
    Icon: ListOrdered,
  },
];

// ── Why ────────────────────────────────────────────────────
const WHY = [
  {
    title: "Skill match + genuine interest",
    desc: "Most tools match keywords. TalentRadar also measures whether a candidate will actually accept the offer — before you pick up the phone.",
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

// ── Sample card ────────────────────────────────────────────
const SAMPLE = {
  name: "Priya Nair",
  title: "Senior Software Engineer",
  company: "Razorpay",
  years: 5,
  location: "Bangalore",
  match: 88,
  interest: 86,
  combined: 87,
  skills: ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
  explanation:
    "Priya demonstrated high enthusiasm and asked thoughtful questions about team structure and tech stack. Her fintech background maps directly to the role. Salary expectation ₹28L is within budget. Available in 45 days.",
};

// ── Page ──────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div className="min-h-screen font-sans" style={{ background: "#FAFAFA", color: "#1A1A1A" }}>

      {/* ── NAV ── */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-[#E0E0E0] px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <RadarLogo size={30} color="#2D7D3E" />
          <span className="text-[19px] font-bold text-[#1A1A1A] tracking-tight">TalentRadar</span>
        </div>
        <nav className="hidden md:flex items-center gap-6">
          <a href="#how-it-works" className="text-[14px] text-[#4A4A4A] hover:text-[#2D7D3E] transition-colors">How it works</a>
          <a href="#why" className="text-[14px] text-[#4A4A4A] hover:text-[#2D7D3E] transition-colors">Why TalentRadar</a>
          <a href="#preview" className="text-[14px] text-[#4A4A4A] hover:text-[#2D7D3E] transition-colors">See output</a>
        </nav>
        <Link href="/scout" className="bg-[#2D7D3E] hover:bg-[#1F5A2B] text-white text-[14px] font-semibold px-5 py-2.5 rounded-lg transition-colors">
          Try it now →
        </Link>
      </header>

      {/* ── HERO ── */}
      <section
        className="relative min-h-[92vh] flex flex-col items-center justify-center px-6 overflow-hidden"
        style={{ background: "linear-gradient(160deg, #1F5A2B 0%, #2D7D3E 45%, #1A3A22 100%)" }}
      >
        <RadarAnimation />

        {/* Floating candidate cards */}
        <FloatingCard name="Arjun Mehta" role="Backend Engineer" score={91} delay={0} x="6%" y="30%" />
        <FloatingCard name="Priya Nair" role="Sr. SWE · Razorpay" score={87} delay={1.5} x="72%" y="18%" />
        <FloatingCard name="Vikram Rao" role="Staff Engineer" score={83} delay={3} x="75%" y="62%" />

        {/* Badge */}
        <div className="relative z-10 inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-white text-[13px] font-medium mb-8">
          <span className="w-2 h-2 rounded-full bg-[#D4AF37] animate-pulse" />
          Built for Catalyst 2026 · AI Recruitment Track
        </div>

        {/* Headline */}
        <div className="relative z-10 text-center max-w-3xl mx-auto">
          <h1 className="text-[52px] md:text-[64px] font-black text-white leading-[1.08] tracking-tight mb-6">
            Find your next hire<br />
            <span style={{ color: "#D4AF37" }}>in minutes,</span>{" "}
            <span className="text-white/80">not days.</span>
          </h1>
          <p className="text-[18px] text-[#D4E8D8] leading-relaxed max-w-xl mx-auto mb-10">
            TalentRadar uses five AI agents to scout candidates, simulate screening conversations, and hand you a transparent ranked shortlist — before your first coffee is cold.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/scout"
              className="group flex items-center gap-2 text-[#1A1A1A] font-bold text-[16px] px-8 py-4 rounded-xl shadow-lg transition-all hover:shadow-2xl hover:scale-[1.03] active:scale-[0.98]"
              style={{ background: "#D4AF37" }}
            >
              Start scouting now
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a href="#how-it-works" className="text-white/70 hover:text-white text-[15px] font-medium transition-colors flex items-center gap-1">
              See how it works ↓
            </a>
          </div>
        </div>

        {/* Bottom fade */}
        <div className="absolute bottom-0 left-0 right-0 h-24 pointer-events-none" style={{ background: "linear-gradient(to bottom, transparent, #FAFAFA)" }} />
      </section>

      {/* ── STATS ── */}
      <section className="px-6 py-12 bg-white border-y border-[#E0E0E0]">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8">
          {STATS.map((stat, i) => (
            <div key={i} className="text-center">
              <p className="text-[36px] font-black text-[#2D7D3E] leading-none mb-1">{stat.value}</p>
              <p className="text-[13px] text-[#4A4A4A] leading-snug">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="how-it-works" className="px-6 py-20 max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <p className="text-[13px] font-bold text-[#2D7D3E] uppercase tracking-widest mb-3">The process</p>
          <h2 className="text-[36px] font-black text-[#1A1A1A] mb-3">How it works</h2>
          <p className="text-[16px] text-[#4A4A4A] max-w-lg mx-auto">Three steps from raw job description to a shortlist you can actually act on.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 relative">
          {/* connector line */}
          <div className="hidden md:block absolute top-16 left-1/6 right-1/6 h-px bg-gradient-to-r from-[#2D7D3E] to-[#D4AF37]" style={{ left: "20%", right: "20%", top: "44px" }} />

          {STEPS.map((step, i) => (
            <div key={i} className="relative flex flex-col items-center text-center px-6 pb-8">
              {/* Icon circle */}
              <div
                className="w-20 h-20 rounded-2xl mb-5 flex items-center justify-center shadow-md relative z-10"
                style={{ background: i === 1 ? "#2D7D3E" : "white", border: `2px solid ${i === 1 ? "#2D7D3E" : "#E0E0E0"}` }}
              >
                <step.Icon className="w-8 h-8" style={{ color: i === 1 ? "#fff" : "#2D7D3E" }} />
              </div>
              <div className="text-[12px] font-bold text-[#2D7D3E] uppercase tracking-widest mb-2">{step.n}</div>
              <h3 className="text-[17px] font-bold text-[#1A1A1A] mb-3 leading-snug">{step.title}</h3>
              <p className="text-[14px] text-[#4A4A4A] leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── WHY ── */}
      <section id="why" className="px-6 py-20" style={{ background: "linear-gradient(180deg, #F5F5F5 0%, #E8F5E9 100%)" }}>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-[13px] font-bold text-[#2D7D3E] uppercase tracking-widest mb-3">Why choose us</p>
            <h2 className="text-[36px] font-black text-[#1A1A1A] mb-3">Built different.</h2>
            <p className="text-[16px] text-[#4A4A4A]">Most ATS tools find who can do the job. We find who <em>wants</em> the job.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {WHY.map((item, i) => (
              <div
                key={i}
                className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-all hover:-translate-y-1"
                style={{ border: "1px solid #E0E0E0", borderTop: "4px solid #2D7D3E" }}
              >
                <div className="w-8 h-8 rounded-full bg-[#2D7D3E] flex items-center justify-center mb-4">
                  <CheckCircle2 className="w-4 h-4 text-white" />
                </div>
                <h3 className="text-[15px] font-bold text-[#1A1A1A] mb-2">{item.title}</h3>
                <p className="text-[13px] text-[#4A4A4A] leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SAMPLE OUTPUT ── */}
      <section id="preview" className="px-6 py-20 max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <p className="text-[13px] font-bold text-[#2D7D3E] uppercase tracking-widest mb-3">Sample output</p>
          <h2 className="text-[36px] font-black text-[#1A1A1A] mb-3">What you actually get</h2>
          <p className="text-[16px] text-[#4A4A4A]">Real data, transparent reasoning, ready to act on — every time.</p>
        </div>

        <div className="rounded-2xl overflow-hidden shadow-xl" style={{ border: "1px solid #333", background: "#1A1A1A" }}>
          {/* Header bar */}
          <div className="flex items-center gap-2 px-5 py-3 border-b border-[#333]">
            <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
            <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
            <div className="w-3 h-3 rounded-full bg-[#28CA41]" />
            <span className="ml-3 text-[#666] text-[12px] font-mono">talentreader.vercel.app/scout</span>
          </div>

          {/* Result row */}
          <div className="p-6 border-b border-[#2A2A2A]">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-full bg-[#2D7D3E] flex items-center justify-center text-white text-[13px] font-bold">#1</div>
              <div>
                <h3 className="text-[18px] font-bold text-white leading-tight">{SAMPLE.name}</h3>
                <p className="text-[13px] text-[#777]">{SAMPLE.title} · {SAMPLE.company} · {SAMPLE.years} yrs · {SAMPLE.location}</p>
              </div>
            </div>
          </div>

          {/* Scores */}
          <div className="grid grid-cols-3 gap-0 border-b border-[#2A2A2A]">
            <div className="p-5 border-r border-[#2A2A2A]">
              <p className="text-[11px] font-bold text-[#777] uppercase tracking-wide mb-1">Match</p>
              <p className="text-[36px] font-black text-[#4A9D5F] leading-none">{SAMPLE.match}</p>
              <div className="h-1.5 w-full rounded-full mt-2" style={{ background: "#2A2A2A" }}>
                <div className="h-full rounded-full" style={{ width: `${SAMPLE.match}%`, background: "#2D7D3E" }} />
              </div>
            </div>
            <div className="p-5 border-r border-[#2A2A2A]">
              <p className="text-[11px] font-bold text-[#777] uppercase tracking-wide mb-1">Interest</p>
              <p className="text-[36px] font-black text-[#4A9D5F] leading-none">{SAMPLE.interest}</p>
              <div className="h-1.5 w-full rounded-full mt-2" style={{ background: "#2A2A2A" }}>
                <div className="h-full rounded-full" style={{ width: `${SAMPLE.interest}%`, background: "#4A9D5F" }} />
              </div>
            </div>
            <div className="p-5">
              <div className="flex items-center gap-1 mb-1"><p className="text-[11px] font-bold text-[#D4AF37] uppercase tracking-wide">Combined</p><Trophy className="w-3 h-3 text-[#D4AF37]" /></div>
              <p className="text-[36px] font-black text-[#D4AF37] leading-none">{SAMPLE.combined}</p>
              <div className="h-1.5 w-full rounded-full mt-2" style={{ background: "#2A2A2A" }}>
                <div className="h-full rounded-full" style={{ width: `${SAMPLE.combined}%`, background: "#D4AF37" }} />
              </div>
            </div>
          </div>

          {/* Skills */}
          <div className="px-6 py-4 border-b border-[#2A2A2A] flex flex-wrap gap-2">
            {SAMPLE.skills.map(s => (
              <span key={s} className="text-[12px] px-3 py-1 rounded-md font-medium" style={{ background: "rgba(45,125,62,0.2)", color: "#4A9D5F" }}>
                <span className="flex items-center gap-1">{s} <CheckCircle2 className="w-3 h-3" /></span>
              </span>
            ))}
          </div>

          {/* Explanation */}
          <div className="px-6 py-5 border-b border-[#2A2A2A]">
            <p className="text-[13px] text-[#999] italic leading-relaxed pl-4" style={{ borderLeft: "2px solid #D4AF37" }}>
              &ldquo;{SAMPLE.explanation}&rdquo;
            </p>
          </div>

          {/* CTA */}
          <div className="px-6 py-5">
            <Link
              href="/scout"
              className="inline-flex items-center gap-2 font-bold text-[14px] px-6 py-3 rounded-lg transition-all hover:scale-[1.02] active:scale-[0.98]"
              style={{ background: "#D4AF37", color: "#1A1A1A" }}
            >
              Get results like this for your role →
            </Link>
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="px-6 py-24 text-center relative overflow-hidden" style={{ background: "linear-gradient(135deg, #1F5A2B 0%, #2D7D3E 100%)" }}>
        <RadarAnimation />
        <div className="relative z-10">
          <h2 className="text-[40px] font-black text-white mb-4 leading-tight">
            Your next great hire<br />is already in the pool.
          </h2>
          <p className="text-[16px] text-[#D4E8D8] mb-10 max-w-lg mx-auto">
            Paste a job description and get a fully evaluated, ranked shortlist in under 3 minutes. No sign-up required.
          </p>
          <Link
            href="/scout"
            className="inline-flex items-center gap-2 font-bold text-[17px] px-10 py-5 rounded-xl shadow-2xl transition-all hover:shadow-3xl hover:scale-[1.04] active:scale-[0.98]"
            style={{ background: "#D4AF37", color: "#1A1A1A" }}
          >
            Start scouting — it&apos;s free
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-[#111] px-6 py-10">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <RadarLogo size={26} color="#4A9D5F" />
            <span className="text-white font-bold text-[16px]">TalentRadar</span>
          </div>
          <p className="text-[13px] text-[#555] text-center">
            Built for Catalyst by Deccan AI · Powered by Groq Llama 3.3 70B & ChromaDB
          </p>
          <div className="flex items-center gap-4">
            <a href="https://github.com/Charan512/TalentHunt" target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#555] hover:text-white transition-colors">GitHub ↗</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
