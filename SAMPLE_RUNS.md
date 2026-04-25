# TalentRadar: Sample Inputs & Outputs

This document showcases standard workflows in the TalentRadar application, from raw Job Description input to the final live-sorted candidate shortlist.

---

## Example 1: Senior Backend Engineer (Payments)

### 1. The Input (Raw Job Description)
The user pastes a raw, unstructured job description into the frontend.

**Input Text:**
> **Job Title**: Senior Backend Engineer (Payments Infrastructure)
> 
> **About Us**:
> We are a fast-growing Fintech startup based in Bangalore, building next-generation payment gateways and fraud-detection pipelines. We process millions of transactions daily, and our engineering team focuses heavily on high-throughput, low-latency architectures. 
> 
> **Role Overview**:
> We are looking for a Senior Backend Engineer with at least 5 years of experience to join our core infrastructure team. You will be responsible for designing idempotent API patterns, migrating legacy systems to microservices, and scaling our databases to handle 50k+ RPS. 
> 
> **Required Skills**:
> - Deep expertise in Python.
> - Production experience with modern frameworks like FastAPI.
> - Strong knowledge of relational databases, particularly PostgreSQL.
> - Experience with containerisation (Docker) and orchestration (Kubernetes).
> - Familiarity with cloud platforms (AWS or GCP).

*[ Placeholder: Insert Screenshot of the Input Form here ]*

---

### 2. Processing (Live Stream & Multi-Agent Pipeline)
Once submitted, the UI enters the dynamic loading state. The backend utilizes Server-Sent Events (SSE) to update the client in real-time as the 5 Autonomous Agents work.

**Pipeline Logs & State:**
1. `Parsing job description...` (Agent 1 extracts skills and seniority)
2. `Searching pool...` (Agent 2 embeds the JD and queries ChromaDB for the Top 5 matches)
3. `Simulating interviews for 5 candidates...` (Agents 3 & 4 converse, Agent 5 scores)

*[ Placeholder: Insert Screenshot of the dynamic loading state here ]*

---

### 3. The Output (Live-Sorted Results)
As each candidate finishes their simulated interview, they pop onto the screen. The UI dynamically re-sorts them based on their `combined_score` (Match + Interest).

**Sample JSON Output Streamed to Client:**
```json
{
  "name": "Kiran Rao",
  "match_score": 83.7,
  "interest_score": 85.0,
  "combined_score": 84.4,
  "rank": 1,
  "explanation": "Kiran has deep experience scaling Python APIs and configuring PostgreSQL for high throughput. During the simulated interview, he asked insightful questions about idempotent API architecture and handling 50k+ RPS, showing high intent and alignment with the payments infrastructure role.",
  "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"]
}
```

*[ Placeholder: Insert Screenshot of the final Candidate Dashboard / Shortlist here ]*

---

## Example 2: Frontend Engineer (React/Next.js)

### 1. The Input
**Input Text:**
> **Role**: Lead Frontend Engineer
> Looking for an expert UI developer to lead our migration to Next.js. Must have deep knowledge of React, Server Components, Tailwind CSS, and state management (Zustand/Redux). You will work closely with design to implement pixel-perfect glassmorphism interfaces and complex animations using Framer Motion. 4+ years of experience required.

*[ Placeholder: Insert Screenshot of the Input Form here ]*

### 2. The Output
The AI evaluates candidates not just on their static skills, but on how they communicate their passion for UI/UX during the simulated conversation.

*[ Placeholder: Insert Screenshot of the Frontend Engineer Shortlist here ]*

---

## How the Scores are Calculated

- **Match Score (Agent 2)**: A purely mathematical semantic similarity score between the parsed JD vector and the candidate's historical vector in ChromaDB.
- **Interest Score (Agent 5)**: A behavioral score derived from reading the transcript of the simulated 6-turn interview. It measures how relevant the candidate's answers and questions were to the *specific* nuances of the JD.
- **Combined Score**: A weighted average controlled by the sliders on the UI (e.g., 60% Match, 40% Interest).
