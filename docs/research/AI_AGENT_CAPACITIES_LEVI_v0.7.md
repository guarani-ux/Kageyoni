# AI Agent Capacities for Communications, Marketing and Media Production
**A practical reference for Levi — Research reference v0.7 (27 October 2026)**  
*Canonical Location: `c:/Kageyoni/docs/research/AI_AGENT_CAPACITIES_LEVI_v0.7.md`*

---

## Author's Preface & Methodological Architecture

> **The Central Axiom:**  
> **A job title is not an agent capability. Specific work, equipped with the right information, methods, tools, and boundaries, can become one.**

### 1. The Core Takeaways
The three fields share methods, but use them for fundamentally different purposes:
* **Communications:** Help people understand, participate, or respond.
* **Marketing:** Understand demand, develop a proposition, and choose how to reach an audience.
* **Media Production:** Turn meaning into an audiovisual experience and coordinate its production.

*“Storytelling”* or *“audience research”* therefore cannot simply mean the same thing everywhere. This guide preserves those differences while identifying reusable methods.

The resulting ten cards are **ways to commission useful work**, not ten installed agents or replacements for professionals.

### 2. How It Was Built
The construction followed this deterministic sequence:
$$\text{Job Descriptions} \longrightarrow \text{Specific Competencies} \longrightarrow \text{Shared Skill Families} \longrightarrow \text{Proposed Agent Procedures} \longrightarrow \text{Actual Exercises} \longrightarrow \text{Revised Guidance}$$

* **Evidence Base:** 48 role records gathered from employer pages, professional associations, public-sector sources, and specialist boards beyond Indeed/LinkedIn (Calgary, Alberta, Canada-remote, plus a closed U.S. field comparator). Closed jobs inform the skills analysis as historical craft evidence, but are distinct from verified active vacancies.
* **Rigorous Separation:** Duties, required qualifications, preferred qualifications, tools, and human authority were strictly separated, yielding **303 source-linked competency relationships**.
* **Primary Practice Grounding:** Professional and institutional standards (IABC, ScreenSkills, StatCan, Google SRE, W3C, Netflix QC, NPR, BBC) were consulted to understand how work is actually performed, rather than treating employer posting language as executable instructions.
* **Consolidation:** 17 initial procedure proposals were consolidated into **10 operational cards**. Each specifies inputs, method, output, tools, human authority decisions, and test status.

### 3. The Reasoning and Inference Involved
At a high level, the analytical work required:
* **Decomposition:** Breaking broad requirements such as “manage campaigns” into research, planning, copy, measurement, and decisions.
* **Comparison:** Identifying what transfers between fields without erasing their conflicting institutional objectives.
* **Hypothesis Formation:** Proposing which specific slices an agent could usefully perform.
* **Counterexample Testing:** Changing facts, resources, permissions, or objectives to observe whether the procedure adapts appropriately.
* **Revision:** Retaining useful results, correcting consequential failures, and narrowing claims where evidence stops.

**The Critical Inference:** Moving from *“an employer requires this”* to *“an agent could assist with this particular task”* is an explicit **design proposal**, not an employer claim.  
*Example:* Lower cost per signup was an observation. It did not prove better creative, because the compared campaigns reached different audiences. Preserving that distinction completely altered the operational recommendation.

### 4. What Verification Actually Involved
Five distinct verification layers, each proving something different:
1. **Source Checks:** Whether job descriptions and practice references supported the claims attributed to them.
2. **Work-Product Checks:** Whether drafts, plans, and analyses answered the brief faithfully and usefully.
3. **Changed-Condition Probes:** Whether outputs adapted when testimony was withdrawn, availability shifted, or approval routes changed.
4. **Technical Checks:** Arithmetic, scheduling constraints, file identity, and actual synthetic video/caption inspection and correction via CLI tools (`ffmpeg`/`ffprobe`).
5. **Document Checks:** Links, counts, version consistency, and visual inspection of all 32 pages.

**Failures were retained.** Early responses were excessively long (1,200–2,170 words) and required explicit shortening rescues. Other work required factual or usability repairs. These were registered as interventions, not independent first-pass successes. Model reviews were not human expert validation; hashes verified file identity, not the truth of the writing.

### 5. The Most Important Finding
In three paired tasks, exact cards were tested against competent direct requests using identical materials. **Both approaches produced useful work. No meaningful advantage for the cards was established.**

The guide’s demonstrated value is as a **structured reference for understanding and specifying work, with bounded examples of use**. It is not evidence that adding an agent framework automatically improves results.

> **Practical Rule for the Operator:**  
> Choose the output you need, use the relevant card to supply missing context or checks, and leave the rest inactive. **The point is better-equipped work, not more machinery.**

---

## 1. Domain Taxonomy & The 14 Skill Families

The 48 roles contribute to an evidence graph of 303 job-to-competency links across 3 research lanes:
* **Communications (C):** 13 roles
* **Marketing (M):** 22 roles
* **Media Production (P):** 13 roles

```
Intent, Evidence & Expression
  F01 Strategy & Planning        (C: 6,  M: 5,  P: 2)  — Direction, positioning, program intent
  F02 Research & Insight         (C: 7,  M: 12, P: 2)  — Audiences, markets, requirements
  F03 Content & Narrative        (C: 7,  M: 6,  P: 3)  — Messages, stories, editorial synthesis
  F04 Distribution & Publishing  (C: 5,  M: 5,  P: 3)  — Channels, publishing, findability

Evaluation, Delivery & Stewardship
  F05 Measurement & Testing      (C: 5,  M: 17, P: 3)  — Outcomes, tests, attribution
  F06 Coordination & Delivery    (C: 8,  M: 9,  P: 9)  — Schedules, approvals, handoffs
  F07 Quality, Risk & Governance (C: 5,  M: 7,  P: 6)  — Standards, checks, privacy, compliance
  F08 Data, Assets & Workflow    (C: 4,  M: 7,  P: 4)  — Records, assets, operational systems

Relationships, Resources & Direction
  F09 Stakeholder & Client Work  (C: 5,  M: 10, P: 2)  — Listening, advice, alignment, negotiation
  F10 Commercial & Resource Ctrl (C: 1,  M: 7,  P: 4)  — Budgets, pricing, vendors, resources
  F11 Leadership & Development   (C: 3,  M: 6,  P: 2)  — Coaching, mentoring, creative direction

Craft Coded in One Lane
  F12 Media-Making & Live Craft  (C: 0,  M: 0,  P: 8)  — Editing, sound, broadcast, live work
  F13 Growth, Lifecycle & Comm.  (C: 0,  M: 7,  P: 0)  — Retention, demand, e-commerce
  F14 Press & Public Response    (C: 5,  M: 0,  P: 0)  — Media relations, issues, crisis response
```

---

## 2. What Transfers and What Changes: Semantic Collisions

A shared word is not yet a shared skill. Identical terms dictate divergent, often conflicting institutional logics:

| Shared Method | Communications (C) | Marketing (M) | Media Production (P) |
| :--- | :--- | :--- | :--- |
| **Understand an Audience** | Identify concerns, access needs, and what people need to understand. Produce message & listening plans. (*C04, C05, C06*) | Compare needs, alternatives, buying/adoption situations. Choose segment & proposition. (*M01, M14, M16*) | Understand viewers and contributors. Choose editorial form, interview questions, scenes, packaging. (*P02, P10, P11*) |
| **Shape a Story** | Explain a change, technical idea, or public issue faithfully. *Persuasion is not always the objective.* (*C01, C09, C11*) | Express a supported promise and connect it to an offer and next action. (*M04, M12, M14*) | Arrange what is seen and heard while preserving context, pacing, and contributor meaning. (*P02, P09, P10*) |
| **Evaluate Results** | Distinguish delivery/reach from understanding, trust, behavior, or organizational outcome. (*C03, C05, C07*) | Distinguish clicks and attributed conversions from qualified demand, retention, or profit. (*M05, M11, M20*) | Distinguish technical acceptance from viewing behavior and editorial success. (*P06, P10, P11*) |
| **Coordinate Work** | Align factual owners, senders, timing, and sensitive approvals. (*C06, C09, C13*) | Align offer, creative, channels, budget, and commercial priorities. (*M01, M07, M18*) | Align assets, crew, locations, resources, edit versions, and delivery specs. (*P04, P05, P12*) |

### Separation of Requirements and Authority
* **Mandate Boundary:** Seniority alters authority and consequence. A model can prepare options for an executive, but does not possess the executive’s mandate. An agent can organize interview notes, but cannot manufacture participant trust or cultural approval. It can plan a shoot, but cannot operate an unconnected camera, make a set safe, or confirm a location is available.

---

## 3. Search Routes Beyond Indeed and LinkedIn

Observed access limits across specialist Canadian discovery channels:
* **IABC Calgary / CPRS Calgary:** Communications, consulting, and engagement. Public text readable; old deadlines persist.
* **Alberta Public Service / City of Calgary / UCalgary:** Public-sector, issues, internal comms. Deep links fail; category != vacancy.
* **GoodWork / WorkInNonProfits / CharityVillage / Reach Hire:** Mission-led comms, fundraising. Compare body deadline with board expiry; distinguish paid from volunteer.
* **Calgary Marketing Association:** Routes postings to member community; inventory not independently browsable.
* **Eluta / FreshGigs:** Canadian discovery. Eluta readable; FreshGigs direct jobs path failed (treat as lead, not verified feed).
* **Jobber / Clio / Critical Mass (Direct ATS):** Product, growth, AI-enablement. Nested ATS requests fail; remote Ontario != remote Alberta.
* **Calgary Arts Development:** Arts, casting, calls. Classified listing != employer vetting.
* **Jeff Gaulin / Broadcast Dialogue:** Journalism, broadcast. Listing display requires JavaScript.
* **AMPIA / NFB Careers:** Screen-industry employer discovery. AMPIA != verified vacancy feed. NFB records expire.
* **Ajax Creative / Klick / Lenbrook:** Production companies. Talent pools must remain separate from current vacancies.

---

## 4. The Universal Operating Contract for Every Card

Every card enforces six mechanical rules:
1. **Deliverable First:** Return requested work first. Add only caveats that affect its use, approval, or next decision. Keep detailed audit trails separate.
2. **Tripartite Info Ledger:** Classify inputs into *Supplied Facts*, *Proposed Choices*, and *Unresolved Information*. Ask only for gaps that materially change work; complete stable portions independently.
3. **Evidence Pointers:** Preserve internal references. Never fabricate research, quotes, outcomes, permissions, or approvals.
4. **Tool Isolation:** Treat connected tools as separate capabilities. Check recipients, data scope, versions, and side effects before execution (previews can execute active webhooks).
5. **Bounded Halting:** Stop dependent actions when required evidence, safe access, or authority is missing. State exact target, reason, and completed work. Do not halt drafting just because deployment is blocked.
6. **Sovereign Authority:** Keep sending, spending, publishing, booking, hiring, clearance, and organizational commitments strictly with the authorized person.

---

## 5. The Ten Procedure Cards

### Card 01: Draft and Sequence Communications
* **Use:** Approved facts need a notice, employee update, issues response, or multilingual counterpart.
* **Method:** 
  1. Separate confirmed facts from proposals/unknowns. Omit irrelevant background without hiding necessary conditions.
  2. Write copy first: meaningful heading, descriptive links, clear action. Adapt expression without inventing benefits.
  3. For change: separate leader rationale from practical impacts. For issues: track claim source, version, scope, owner. *Vendor recovery != local restoration; requests and retries are not people.* Separate public updates from internal resolution estimates.
  4. Multilingual: draft both versions. Preserve names, quantities, conditions, negation, uncertainty, action. Use approved terminology. Flagging is a proposed issue, not expert linguistic adjudication.
  5. Check text, then isolate real-page checks (metadata, semantic headings, links, text expansion). Do not claim accessibility validation from copy alone.
* **Human Authority:** Sensitive disclosure, cultural decisions, release.

### Card 02: Plan Engagement and Summarize Stakeholder Input
* **Use:** A decision needs stakeholder input or authorized submissions need synthesis.
* **Method:**
  1. Match public promise to real decision rights (informing, consultation, delegated choice).
  2. Define accessible channels, analysis rules, realistic report-back points.
  3. Preserve raw input. Distinguish import rows, responses, contributors, arguments. Remove duplicate imports from response counts, but retain distinct people's shared wording. Preserve minority concerns.
  4. State eligible denominators. Self-selected frequency is neither population prevalence nor a vote.
  5. Emit synthesis, decision-response matrix, public copy (considered, acted on, declined, pending).
* **Human Authority:** Participation promises, permissions, consequential interpretation, final commitments.

### Card 03: Research an Audience and Create Positioning Options
* **Use:** An offer needs an audience choice and a defensible promise.
* **Method:**
  1. State the decision and what evidence could overturn it. Separate observed behavior, reported experience, stakeholder beliefs.
  2. Choose method for question: exploratory interviews vs. population estimates. Convenient interviews are not market-size estimates.
  3. Map observation $\to$ interpretation $\to$ decision with source IDs. Do not discard isolated decisive contradictions.
  4. Compare audiences by need, offer fit, reachability, commercial relevance, confidence. No purchase is a legitimate alternative.
  5. Create two distinct proposition routes (audience, promise, mechanism, evidence, limitations).
  6. Define continuation rules before tests. Free pilots do not establish market demand.
* **Human Authority:** Market priority, product truth, commercial commitments.

### Card 04: Create an Integrated Campaign Plan
* **Use:** An objective needs a campaign idea, channel sequence, and production handoff.
* **Method:**
  1. Specify whose behavior changes, by when, and why. Separate business results from delivery metrics (target != forecast).
  2. Compare routes differing in audience barrier or value demonstration, not just slogans. State what is sacrificed.
  3. Develop chosen route (tension, supported promise, proof). Write complete assets.
  4. Cost the sequence: check hours, approvals, revision windows. Expose approve-as-delivered vs. defer choices.
  5. Build work packages (input, deliverable, owner, dependency, deadline). Define weak, promising, inconclusive signals.
* **Human Authority:** Creative preference, resource allocation, commitments, launch.

### Card 05: Interpret Performance and Choose the Next Move
* **Use:** A performance decision, budget-risk readout, or test proposal is required.
* **Method:**
  1. Reconcile denominators, windows, duplicates, costs. Check billing campaign types (daily budget != hard ceiling).
  2. Match measures: comms = understanding/behavior; marketing = qualified demand; video = viewing criteria. Output volume != impact.
  3. Separate observation, attribution credit, and causal evidence. Attribution modeling != proof of incremental lift.
  4. Offer real choices: act under stated uncertainty, run a learning test, or defer. A powered experiment is not a prerequisite to every sensible operational decision.
  5. Define tests: assignment, primary outcome, comparison, budget, stopping rules.
* **Human Authority:** Acceptable uncertainty, spend, exclusions, launch.

### Card 06: Check a Lifecycle Journey and Draft Its Messages
* **Use:** Segmented journeys need path review and branch copy.
* **Method:**
  1. Establish entry, suppression, branch order, delay, exit rules. Today's simulation cannot explain historical incidents.
  2. Predict fixture paths and timing before execution. Compare routing with editorial intent.
  3. Draft complete branch messages with missing-data fallbacks. Label repairs as proposals, not deployed changes.
  4. Inspect side-effects: Braze Canvas preview executes Connected Content; test messages can execute webhooks. HubSpot Test simulation performs no actions; Send preview sends live emails.
  5. Return path table, consequential findings, copy, next permitted checks. Clean templates do not make legacy instances safe.
* **Human Authority:** Recipient scope, contact policy, edits, endpoint effects, live sends.

### Card 07: Audit Search Readiness and Draft Useful Page Copy
* **Use:** An organic search audit or AI-search fix is requested.
* **Method:**
  1. Separate crawl access, index inclusion, snippet permissions, content usefulness. HTML is not a live ranking check.
  2. Inspect robots.txt, HTML/HTTP controls, discovery links together. A crawl block is not privacy protection and prevents reading noindex. Nosnippet != noindex.
  3. Compare structured data with visible facts. Valid syntax does not establish rich-result eligibility.
  4. Write copy: page-specific meta description, heading, body, next step. Answer questions without keyword padding.
  5. Google AI Overviews: links must be indexed and snippet-eligible. No special schema guarantees inclusion.
  6. Prioritize by evidence, impact, effort. Search controls are not authentication.
* **Human Authority:** Visibility/privacy objectives, deployment authorization.

### Card 08: Develop a Video Concept Script and Production Plan
* **Use:** An idea needs a concept, a brief needs a script, or approved material needs a production plan.
* **Method:**
  1. Choose viewer takeaway and feasible form. Patient observation and no music can be legitimate choices.
  2. Give images and sounds a purpose. Illustration does not prove a spoken claim.
  3. **Write complete Audio Components before Video Components.** Separate narration, speech, nat sound, screen copy from directions. Invent no unseen action.
  4. Sum segments and capacities. Listen without reading ahead. *Arithmetic does not establish pacing or runtime.*
  5. Intersect people, location, kit windows; reserve one-time events. Schedule proof, setup, pack, travel, capture, handoff with local slack. Report infeasible coverage rather than hallucinating crew teleportation.
  6. Return editorial checks; plan captions, description, transcripts early.
* **Human Authority:** Contributor relations, creative acceptance, rights, safety, bookings, capture.

### Card 09: Reconcile Media Versions and Turnover
* **Use:** Feedback, approval, or editorial transfer could refer to the wrong asset.
* **Method:**
  1. Establish exact asset and approved state. Filenames and stack position do not prove accepted versions.
  2. Attach feedback to correct version. Approval of a master does not approve a derivative or later edit.
  3. For turnover: verify saved project and linked media before export. Inspect translation warnings (FCP XML).
  4. Compare import against reference (effects, transitions, nested sequences, audio). Export completion != equivalence.
  5. Return smallest exception list (owner, affected version/timecode, required evidence).
* **Human Authority:** Creative acceptance, ambiguous feedback, editorial fidelity, release approval.

### Card 10: Check a Release Package and Prepare the Handoff
* **Use:** Media packages are proposed for delivery or publication.
* **Method:**
  1. Reconcile source, derivative, and caption identities. Preserve originals and SHA-256 hashes.
  2. Map permissions to intended use. Actual license terms govern; Adobe Stock examples cannot clear unidentified audio.
  3. Compare manifest declarations with measured streams: width, height, duration, aspect ratio, frame rate via `ffprobe`.
  4. View picture samples on both sides of edit/caption boundaries. Compare caption words/cue times with approved meaning. *Missing negation is a critical content defect.* Distinguish decoded media from continuous playback.
  5. Re-probe new bytes after correction. Return release disposition. Decoder success != perceived pacing or accessibility.
* **Human Authority:** Legal interpretation, contributor consent, creative sign-off, corrections, release.

---

## 6. What the Bounded Model Trials Proved

### The Verbosity Tax and Prompted Rescues
* Initial unconstrained model runs produced massive over-generation. Targeted constraints were required to achieve operational usability:
  - *Communications Change Notice:* 1,255 words $\rightarrow$ **338 words** (email + 6-item FAQ + $\le 3$ notes).
  - *Marketing Performance Readout:* 1,712 words $\rightarrow$ **567 words** (balanced uncertainty vs. testing).
  - *Media Release Review:* 2,170 words $\rightarrow$ **536 words** (combined overlapping ledgers into actions).
* Revisions were **prompted rescues**, not independent first-pass successes.

### Key Empirical Failure Modes Observed
1. **The Attribution Trap (Card 05):** Fixture A (\$400, 20 signups, new visitors, CPA \$20) vs. Fixture B (\$300, 27 signups, prior attendees, CPA \$11.11). Models initially declared Creative B superior due to a 44.4% lower CPA. Corrected reasoning recognized audience selection bias ($Z \to X$ and $Z \to Y$).
2. **Missing Negation in Media Subtitles (Card 10):** A synthetic MP4 measured `640x360` (10s) against an approved `360x640` (8s) brief. Its SRT caption dropped the word *"not"* (*"was [not] repairable"*), reversing legal meaning, while the cue overran EOF. Local `ffmpeg`/`ffprobe` commands caught and repaired the defect.
3. **The Locomotion Impasse (Card 08):** 1 camera/sound unit covering 4 beats. Curator window moving from 09:35 to 09:50 made coverage physically impossible due to packing, travel, and setup times. The model correctly reported an incomplete, approval-dependent plan rather than hallucinating crew teleportation.

---

## Appendix A: Candidate Procedure Crosswalk
Consolidation of 17 original candidate procedures into 10 operational cards:
* `CAP-C-CHANGE` (Change message sequence) $\to$ **Card 01**
* `CAP-C-ISSUES` (Evidence-bound issues response) $\to$ **Card 01**
* `CAP-C-LISTEN` (Stakeholder input loop) $\to$ **Card 02**
* `MCORE01` (Integrated campaign planning) $\to$ **Card 04**
* `MCORE02` (Audience research & proposition) $\to$ **Card 03**
* `MCAP01` (Experiment planning & evaluation) $\to$ **Card 05**
* `MCAP02` (Lifecycle journey QA) $\to$ **Card 06**
* `MCAP03` (Paid performance & budget risk) $\to$ **Card 05**
* `MCAP04` (Organic search readiness) $\to$ **Card 07**
* `MC01` (Production brief & scope) $\to$ **Card 08**
* `MC02` (Schedule resources & cost) $\to$ **Card 08**
* `MC03` (Review version & asset control) $\to$ **Cards 09 & 10**
* `MC04` (Editorial turnover exceptions) $\to$ **Card 09**
* `MC05` (Delivery QC & correction planning) $\to$ **Card 10**
* `MC06` (Short-form repurposing) $\to$ **Cards 08 & 10**
* `MC07` (Publication experiment analysis) $\to$ **Card 05**
* `MC08` (Rights evidence & intended usage) $\to$ **Card 10**

---

## Appendix B: The 48-Role Job Evidence Register

| ID | Employer & Role | Observed State (27 Oct 2026) |
| :--- | :--- | :--- |
| **C01** | Primary Care Alberta · Senior Communications Advisor | Listed; deadline 29 Oct |
| **C02** | Gov of Alberta (Executive Council) · Sr Media Relations Advisor | Listed; in office Edmonton |
| **C03** | Tailscale · Head of Communications | Listed; no deadline |
| **C04** | Indspire · Sr Communications Advisor - French Language Strategy | Listed; national remote |
| **C05** | Alberta Environmental Network · Communications Coordinator | Listed; open until filled |
| **C06** | Calgary Foothills PCN · Sr Communications Consultant | Association listing; widget unverified |
| **C07** | Health Quality Alberta · Digital Communications Lead | Closed; historical evidence |
| **C08** | City of Edmonton · Sr Communications Advisor | Indexed description inspected; live unverified |
| **C09** | Royal Canadian Mint · Advisor, Employee Communications | Closed; historical evidence |
| **C10** | CARFAC Alberta · Communications Coordinator | Closed; historical evidence |
| **C11** | OceanMD (WELLSTAR) · Communications Strategist | Listed; no deadline |
| **C12** | Alberta Magazine Publishers Association · Comms Manager | Closed; deadline passed |
| **C13** | The Nonprofit Chamber · Comms & Engagement Coordinator | Listed; open until filled |
| **M01** | Pizza Hut Canada · Marketing Manager | Employer detail with Apply; ON remote, AB unknown |
| **M02** | Marvel Marketing · Marketing Operations Coordinator | Current employer index |
| **M03** | Acuity Insights · Senior Growth Marketing Manager | Indexed description; live unverified |
| **M04** | Directive · Customer Marketing Manager | Indexed description; live unverified |
| **M05** | Optro · Senior Manager, Marketing Analytics | Indexed description; vacancy unverified |
| **M06** | SAIT · Performance Marketing Specialist | Employer detail; future deadline |
| **M07** | Meridian15 · Account Manager | Employer detail; future deadline |
| **M08** | Jobber · AI Marketing Enablement Manager | Current index; named hubs exclude Calgary |
| **M09** | Jobber · Partner Marketing Manager | Current index and detail |
| **M10** | Jobber · Senior Brand Partnerships Manager | Current index and detail |
| **M11** | Copper · Manager, Demand Generation | Employer detail; salary currency unspecified |
| **M12** | Viral Nation · Senior Manager, Content Marketing | Employer detail; salary lower bound malformed |
| **M13** | DoorDash Canada · Associate Manager, Consumer Retention | Employer detail; pay range BC specific |
| **M14** | Clio · Senior Product Marketing Manager | Employer detail; Calgary listed; Apply target preview |
| **M15** | Clio · Pricing Analyst | Current index and detail |
| **M16** | WJ Agency · Senior Marketing Strategist | Expired; historical evidence |
| **M17** | One Core Media · Senior SEO Specialist | Marked OPEN; March info may be stale |
| **M18** | Hope Mission · Fundraising Project Administrator | Employer detail with Apply |
| **M19** | Londre Bodywear · Ecommerce Marketing Manager | Employer careers detail |
| **M20** | Thrive Digital · Associate Director, Strategy | Existing vacancy stated; Canada remote |
| **M21** | Explorer Research · Research Analyst / Shopper Research | Readable description; ON residency required |
| **M22** | Angus Reid · Research Director | Employer detail and index; listed, unconfirmed |
| **P01** | AGAT Laboratories · Multimedia Marketing Specialist | Employer detail and form; no deadline |
| **P02** | Lenbrook · Video Content Specialist / Video Producer | Employer detail; no deadline |
| **P03** | Bell Media · Producer I | Deadline passed; alternate page says filled |
| **P04** | Company 3 / Curated · VFX Producer (General Submission) | Future talent pool; not an active vacancy |
| **P05** | National Film Board of Canada · Flex Coordinator Operations | Current employer board and detail |
| **P06** | Brown Bag Films · Post Production Coordinator | Undated employer PDF; vacancy unverified |
| **P07** | Ajax Creative · Executive Producer - Canada | Not actively hiring; talent pipeline |
| **P08** | Ajax Creative · Intake Producer | Detail absent from current index; uncertain |
| **P09** | Digital Shift · Video Editor | Employer careers page and application |
| **P10** | Ledcor · Video Communications Editor | Employer detail and application |
| **P11** | Yaqeen Institute · Digital Producer | Current employer board and detail |
| **P12** | Klick · Associate Director, Broadcast Creative Producer | Existing vacancy stated; current index |
| **P13** | Bell Media · ENG Technician | Closed U.S. comparator; direct page says filled |

---

## Appendix C: Primary Practice Sources
* **Cross-Domain:** IABC (Global Standard), CIM (Professional Marketing Framework), AMA (Marketing Competency Model), ScreenSkills (Skills Checklists & Unscripted TV), AMEC (Integrated Evaluation Framework), W3C WAI (Audio/Video Accessibility).
* **Communications Methods:** Prosci (Change Management Checklist), US CDC (Risk Communication Principles), Health Canada / PHAC (Public Engagement Guidelines 2023), IAP2 (Spectrum of Public Participation 2024), Google SRE (Managing Incidents).
* **Marketing & Search:** Google Search Central (Robots.txt, Meta Tags, Title Links, Snippets, Structured Data, Technical Requirements, Helpful Content, AI Features), Google Ads (Experiments, Conversion Lift, Bidding Tests, Spending Limits), Google Analytics (Attribution), HubSpot (Workflow Testing & Suppression), Braze (Personalization Preview & Test Delivery), Statistics Canada (Survey Questions & Quality Guidelines 6th Ed), GOV.UK (User Research Interviews, Analysis & Recruitment), Strategyzer (Value Proposition & Test Card), Ipsos InnoQuest (Order Effects in Monadic Testing).
* **Media Production:** Associated Press (Telling the Story), Alison MacAdam / NPR Training (Radio Script Structure & Ear-Editing), BBC (Shot Planning & Interviewing), ScreenSkills (1st AD Skills), Adobe Premiere (XML Export), Frame.io (V4 Versioning), Netflix (Metadata Redelivery & QC Reports), YouTube (Title & Thumbnail Testing), Adobe Stock (Audio Licensing).

---

## Appendix D: Complete Script Examples (Cedar Repair Circle)

### The 45-Second Orientation Script (Patient Observation)
* `00–05s`: **Audio:** Silence. No narration or added event sound.  
  **Video:** V01, static wide arrival with unplugged lamp. No text or hook graphic.
* `05–11s`: **Audio:** Proposed narration, *“At intake, describe your item.”* Leave remaining space quiet.  
  **Video:** V02, hands resting lamp beside blank card headed “Item”. Do not imply writing. Caption exactly.
* `11–19s`: **Audio:** Proposed narration, *“A volunteer discusses whether the team can help.”* Pause afterward; no invented conversation.  
  **Video:** V03, contiguous model-label gesture then listening, if both fit. Caption exactly.
* `19–37s`: **Audio:** V04, whole supplied participant excerpt with quiet room tone: *“I came hoping we could fix my lamp. It wasn't repairable that day, but I left knowing what part to look for.”* No overlapping narration.  
  **Video:** Remain on V04 for complete take. Exact speech as caption. Do not generalize into a parts-advice promise.
* `37–41s`: **Audio:** Proposed narration, *“Some items cannot be repaired at the session.”*  
  **Video:** V05, departure with the same unrepaired lamp. Caption exactly.
* `41–45s`: **Audio:** Proposed narration, *“Ask the repair table what items they can accept.”*  
  **Video:** G01, high-contrast text held throughout: *“Ask the repair table what items they can accept.”* No duplicate caption, logo, URL, or booking info.

### The 30-Second Changed-Constraint Script (Silent Observation, Consent Withdrawn)
* `00–06s`: **Audio:** Silence; no spoken words.  
  **Video:** V01, ordinary static-wide arrival with unplugged lamp. No screen text.
* `06–12s`: **Audio:** Silence; no spoken words.  
  **Video:** V02, hands beside blank card headed “Item”. Overlay: *“At intake, describe your item.”*
* `12–19s`: **Audio:** Silence; no spoken words.  
  **Video:** V03, 7-second contiguous excerpt from gesture/listening take. Keep lamp unplugged. Overlay: *“A volunteer discusses whether the team can help.”*
* `19–24s`: **Audio:** Silence; no spoken words.  
  **Video:** V05, departure with unrepaired lamp. Overlay: *“Some items cannot be repaired at the session.”*
* `24–30s`: **Audio:** Silence; no spoken words.  
  **Video:** G01, final card held throughout: *“Ask the repair table what items they can accept.”*
