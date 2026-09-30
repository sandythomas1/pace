# Spec: PACE Running Assistant

> **Phase:** Specify · **Status:** draft · **Owner:** sandythomas1 · **Date:** 2026-09-30
> The *what* and *why*. No implementation detail — that belongs in `plan.md`.
> **Decided 2026-09-30:** the model is **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`). Options, costs,
> and rationale are in [model-options.md](model-options.md).

## Problem
PACE shows charts and totals, but answering a specific question such as "Am I on track for a
sub-2:00 half?", "How did my long runs change this month?", or "What should my easy pace be?"
still means reading several screens and doing the maths yourself. The runner wants to ask a question
in plain language and get a short, correct answer grounded in their own data, without handing a
private training history to an always-on cloud service or paying for a general-purpose chatbot that
drifts into unrelated topics.

## Goals
- Answer natural-language questions about the runner's own runs, trends, and goals. At least 90% of
  a fixed evaluation set of 40 questions is answered correctly, with every quoted number matching
  PACE's own figures.
- Give a race-time prediction for a supported distance. It states its method, a range, and the data
  it relied on, and declines when the data is insufficient.
- Stay strictly on running. At least 95% of an off-topic and adversarial evaluation set is refused
  or redirected.
- Keep running costs trivial. Normal personal use (about 100 questions a month) costs under
  **US$1/month**, with a hard spending cap that cannot be exceeded.
- Keep PACE fully usable when the assistant is disabled, unconfigured, offline, or over budget.

## Non-Goals
- **No actions on the runner's data in v1.** The assistant does not create, edit, or delete runs,
  plans, goals, or settings.
- **No medical care.** No diagnosis, injury treatment, or nutrition or medication advice beyond general,
  widely accepted running guidance, and no replacement for a clinician or coach.
- **No general chatbot.** It does not answer questions outside running, even simple ones.
- **No training of the model on the runner's data**: no fine-tuning and no custom model.
- **No multiple users.** No shared or hosted deployment: PACE stays single-user and loopback-only.
- **No voice, images, or file uploads** to the assistant.
- **No push notifications** and no proactive coaching messages. The assistant only speaks when asked.
- **No other data sources.** Weather, sleep, HRV, and similar data are out of scope unless PACE
  already stores them.

## User Stories
- As a **runner**, I want to **ask "how far did I run in September and how does it compare to August?"**,
  so that **I get a direct answer without building the comparison myself**.
- As a **runner training for a half marathon**, I want to **ask "what finish time can I realistically
  expect?"**, so that **I can set a goal grounded in my recent training**.
- As a **runner**, I want **the assistant to explain which runs and which method a prediction used**,
  so that **I can judge how much to trust it**.
- As a **runner**, I want to **ask general running questions (e.g. "what is a tempo run?")**, so that
  **I can learn without leaving PACE**.
- As a **privacy-conscious runner**, I want to **see exactly what data is sent to the AI provider and
  turn the assistant off**, so that **I stay in control of my training history**.
- As a **cost-conscious runner**, I want **a monthly spending cap and visible usage**, so that
  **the assistant can never produce a surprise bill**.

## Functional Requirements

### Access and configuration
1. The assistant MUST be off by default. It MUST become active only after the runner explicitly
   enables it and provides provider credentials. [NEEDS CLARIFICATION: which provider path(s) must
   be supported (see Open Questions Q1)?]
2. Provider credentials MUST NOT be written to disk in plaintext, shown back in full in the UI,
   written to logs, or included in exports. They MUST meet the same protection standard as the
   Garmin session.
3. The runner MUST be able to disable the assistant and remove stored credentials in one action.
   PACE's other features MUST be unaffected.
4. Before first use, the assistant MUST show a disclosure. It names the provider, lists the categories
   of data sent, and states the provider's data-use terms for the selected tier. The runner must
   acknowledge it before continuing.

### Answering questions
5. The runner MUST be able to type a question and receive a text answer inside PACE.
6. Answers about the runner's data MUST be grounded in PACE's stored runs, plans, and settings.
   The assistant MUST NOT invent runs, dates, or values.
7. Every number in an answer that describes the runner's data (distances, times, paces, counts, dates,
   heart rate) MUST match what PACE's own calculations produce for the same question. The model MUST
   NOT be the source of arithmetic.
8. Answers MUST use the runner's configured units (mi or km) and PACE's time and pace formats.
9. When a question cannot be answered from the available data, the assistant MUST say so and say what
   data is missing. It MUST NOT guess.
10. Answers SHOULD say which runs or date range they were based on, e.g. "Based on 14 runs from
    Sep 1–29".
11. The assistant MUST NOT treat sample/preview runs as the runner's data.
12. The assistant MUST support follow-up questions within a conversation, e.g. "and in August?".
    [NEEDS CLARIFICATION: Q4, should conversations persist across restarts?]

### Predictions
13. The assistant MUST produce race-time predictions for the supported distances.
    [NEEDS CLARIFICATION: Q5, half marathon only, or also 5K / 10K / marathon?]
14. Each prediction MUST include a point estimate and a range. It MUST name the method used, e.g.
    "based on your recent 10K-equivalent effort", and list the specific runs it relied on.
15. A prediction MUST be refused, with a reason, when there is not enough recent data.
    [NEEDS CLARIFICATION: Q6, what minimum recent data is required to predict at all?]
16. Given the same stored data, the prediction's numbers MUST be the same every time they are
    requested. Only the wording may vary.
17. Predictions MUST be labelled as estimates, not guarantees, and MUST be kept distinct from the
    runner's own saved goal.

### Scope and safety
18. The assistant MUST refuse or redirect requests unrelated to running. The refusal MUST be brief
    and polite and suggest what it can help with.
19. For injury, pain, or medical questions, the assistant MUST give only general information and MUST
    recommend a qualified professional. For symptoms that sound urgent, e.g. chest pain or fainting,
    it MUST tell the runner to stop and seek medical help.
20. Text from the runner's data (activity names, notes, shoe names, anything imported from Garmin or
    files) MUST be treated as data, never as instructions. Content placed there MUST NOT change the
    assistant's scope or behaviour.
21. The assistant MUST NOT reveal its configuration, credentials, or internal instructions when asked.

### Privacy, cost, and resilience
22. Only the minimum data needed for the question MAY be sent to the provider.
    [NEEDS CLARIFICATION: Q3, may free-text notes and activity names be sent?]
23. The runner MUST be able to view the data that was sent for the most recent answer.
24. PACE MUST enforce a configurable monthly spending cap. Requests that would exceed it MUST be
    blocked with a clear message. The UI MUST show estimated spend for the current month.
    [NEEDS CLARIFICATION: Q2, the default cap]
25. When the provider is unreachable, rate-limited, or returns an error, the assistant MUST show a
    plain-language message and a retry option. PACE MUST keep working.
26. A single question MUST NOT be able to trigger unbounded provider calls. Each question has a fixed
    maximum number of calls and a fixed maximum cost.

## Non-Functional Requirements
- **Performance:** The first visible part of an answer appears within 3 s at p95, and a full answer
  within 10 s at p95, on a normal home connection. Preparing the data for a question adds less than
  300 ms with 5,000 stored runs.
- **Cost:** Under US$0.01 per question on average. The monthly cap is enforced before sending, so it
  holds even when usage estimates are off.
- **Security:**
  - The server stays loopback-only.
  - The browser page MUST NOT contact third-party services directly, and the existing
    Content-Security-Policy MUST NOT be loosened.
  - Existing session, CSRF, and Host/Origin checks apply to all assistant endpoints.
  - Input is length-limited, and responses are escaped before rendering.
  - Prompt-injection resistance is covered by FR 20.
- **Privacy:**
  - Logs MUST NOT contain question text, answers, run data, or credentials; they record only metadata
    such as timing, token counts, and error class.
  - The disclosure (FR 4) must be accurate for the chosen provider tier.
- **Reliability:** The assistant degrades as described in FR 25. Its failures never block syncing,
  imports, or other pages.
- **Accessibility:**
  - Meets WCAG 2.1 AA.
  - Fully usable by keyboard.
  - Streaming or new answers are announced to screen readers.
  - Visible focus states and a non-colour-only error state.
- **Scale:** One user, up to about 5,000 stored runs and about 300 questions/month. No concurrency
  requirements beyond one active question at a time.
- **Portability:** Works on the Windows and macOS configurations PACE already supports.

## Acceptance Criteria
- [ ] With the assistant disabled or unconfigured, every existing PACE test passes, and no request is
      made to any AI provider.
- [ ] A 40-question evaluation set runs against synthetic run data, covering totals, comparisons,
      trends, pace zones, "not enough data", and follow-ups. It scores at least 90% correct, and every
      quoted number matches PACE's calculations.
- [ ] A 40-prompt off-topic and adversarial set scores at least 95% correct refusal or redirection. It
      includes prompt injection planted in activity names and notes.
- [ ] A prediction for a supported distance shows an estimate, a range, a method, and the runs used.
      With insufficient data it refuses and gives a reason. Asking twice returns identical numbers.
- [ ] A medical-symptom prompt set always recommends a professional, and urgent symptoms always
      trigger the stop-and-seek-help message.
- [ ] Credentials are never found in plaintext on disk, in logs, in exports, or in API responses
      (verified by test).
- [ ] With the monthly cap set to $0.01, the next question is blocked with a clear message, and no
      provider call is made.
- [ ] If the provider is offline, rate-limited, or returns an error, the assistant shows a friendly
      message and the rest of PACE keeps working (verified by test with a simulated provider).
- [ ] The "data sent" view for the last answer shows only the permitted fields (FR 22).
- [ ] The assistant's cost is measured and reported over the evaluation set. It averages under
      US$0.01 per question.
- [ ] The accessibility checks listed under Non-Functional Requirements pass.

## Open Questions
- **Q1** [NEEDS CLARIFICATION: The model is now decided (Gemini 3.5 Flash-Lite). What remains is how
  to reach it:
  (a) a Google AI Studio API key on the **paid** tier, or
  (b) GCP Vertex AI.

  Should the **free** AI Studio tier be allowed at all? Its terms let Google use prompts to improve
  its products and allow human review, and they say not to submit personal information.
  *Recommendation: (a) a paid AI Studio key, and block the free tier for real run data.*]
- **Q2** [NEEDS CLARIFICATION: What should the default monthly spending cap be? *Suggested: US$2.*]
- **Q3** [NEEDS CLARIFICATION: May free-text fields (run notes, activity names, shoe names) be sent to
  the provider? They make answers richer but can contain personal details. Should heart rate be sent?]
- **Q4** [NEEDS CLARIFICATION: Should conversations persist across PACE restarts (stored locally), or
  only for the current session? Should history be included in JSON exports?]
- **Q5** [NEEDS CLARIFICATION: Which prediction distances are in scope: half marathon only, or also
  5K / 10K / marathon?]
- **Q6** [NEEDS CLARIFICATION: What is the minimum data needed to predict, e.g. at least one run of
  5 km or more within the last 6 weeks and at least N runs? And how wide should the stated range be?]
- **Q7** [NEEDS CLARIFICATION: Is general running coaching in scope, e.g. "what should my easy pace
  be?" and "suggest a workout for this week", or only questions about recorded data plus
  definitions?]
- **Q8** [NEEDS CLARIFICATION: Should the assistant consider the Mission Inn course details (elevation,
  course profile) when discussing race-day pacing?]
- **Q9** [NEEDS CLARIFICATION: Is English-only acceptable for v1?]

## References
- Constitution: `~/.claude/CLAUDE.md`, `~/development/memory/engineering_principles.md`
- Candidate models and cost estimates: [model-options.md](model-options.md)
- PACE security model: [../../SECURITY.md](../../SECURITY.md) (loopback-only, CSP, credential storage)
- Gemini API terms (free vs paid data use): https://ai.google.dev/gemini-api/terms
