# AI College Assistant — Requirements Specification

**Status:** Draft for stakeholder review  
**Version:** 0.1  
**Purpose:** Define a small, classroom-demonstration assistant before implementation. College-specific policies and operational choices remain unconfirmed and must not be inferred by the implementation team.

## 1. Stakeholders

| Stakeholder | Interest / responsibility |
|---|---|
| Students (primary users) | Ask questions and receive understandable, source-grounded information. |
| Faculty / college content owners | Provide and approve the authoritative information the assistant may use. |
| College administrator / sponsor | Approve the intended use, supported topics, audience, and deployment conditions. |
| Project team / maintainers | Implement, test, secure, document, and maintain the demonstration. |
| Lecturer / evaluator | Assess the system as a B.Tech Software Engineering demonstration. |
| Privacy / security representative (if applicable) | Advise on permitted data, retention, access, and deployment controls. |

## 2. Scope

### 2.1 Proposed MVP scope

The MVP is a small web application in which a user can submit a question about approved college information, receive an answer grounded in the configured knowledge base, and see the supporting source. If the available material does not support an answer, the assistant must say that the source does not provide enough information.

The MVP is intended for classroom demonstration. It should use a small, curated, non-sensitive knowledge base and a simple browser interface. SQLite is the source of truth for any transactional data that is introduced; whether the MVP needs to persist queries or other user data is undecided.

### 2.2 Out of scope unless approved later

- Access to student information systems, grades, attendance, fees, or other personal records.
- Authentication, student-specific authorization, or personalized answers.
- Performing transactions, changing records, sending messages, or taking actions on a user's behalf.
- Replacing official college channels or giving binding policy determinations.
- Broad web search or answers from sources not approved for the knowledge base.
- Production-scale availability, multi-college tenancy, or a mobile application.
- External LLM/API use, analytics, or telemetry until their necessity and data handling are approved.

## 3. Functional requirements

| ID | Requirement | Priority / status |
|---|---|---|
| FR-01 | The system shall provide a browser-accessible interface for submitting a natural-language question and viewing a response. | Must |
| FR-02 | The system shall accept questions only within configured input limits and reject missing, blank, malformed, or over-limit input with a clear validation response. | Must; exact limits TBD |
| FR-03 | The system shall search only the knowledge sources configured and approved for this demonstration. | Must |
| FR-04 | The system shall answer using information supported by retrieved knowledge-base content and shall not invent college policies or facts. | Must |
| FR-05 | When the configured sources do not contain enough information to answer, the system shall state that the source does not provide enough information rather than guess. | Must |
| FR-06 | For an answer based on retrieved content, the system shall identify the supporting source in a way the user can understand. | Must; citation detail TBD |
| FR-07 | The system shall treat retrieved documents as untrusted data and shall not follow instructions contained in those documents. | Must |
| FR-08 | The system shall not perform write actions on college systems or expose tools beyond narrowly scoped, read-only operations. | Must |
| FR-09 | The system shall return clear, non-sensitive error messages when a request cannot be processed, without exposing implementation details. | Must |
| FR-10 | Authorized maintainers shall be able to update the approved knowledge content through a documented process. | Must; process/authorization TBD |
| FR-11 | The system shall not claim that an answer is official, current, or binding unless that status is explicitly established by the source owner. | Must |
| FR-12 | The system shall provide a clear indication that it is a demonstration assistant and that official college channels should be used for confirmation, if the college approves that wording. | Proposed; wording TBD |

## 4. Non-functional requirements

| ID | Requirement | Acceptance measure / status |
|---|---|---|
| NFR-01 | The design shall remain simple enough to explain in a B.Tech Software Engineering lecture. | Use the approved stack: Python 3, FastAPI, SQLite, HTML/CSS/JavaScript, and pytest; avoid unnecessary frameworks and cloud services. |
| NFR-02 | The codebase shall use small, readable modules with business rules outside any LLM. | Reviewable separation between request handling, retrieval/answer rules, and data access. |
| NFR-03 | The system shall be testable without real student or company data. | Automated tests use synthetic or fictional content. |
| NFR-04 | Each implemented feature shall have relevant automated tests. | pytest covers expected behavior, validation, and relevant failure/edge cases. |
| NFR-05 | The system shall preserve SQLite as the source of truth for transactional data. | No conflicting in-memory or external source of truth for such data. |
| NFR-06 | The system shall provide understandable feedback for successful, unsupported, invalid, and failed requests. | Responses distinguish these outcomes without success-shaped fallbacks. |
| NFR-07 | The application shall be runnable locally using documented setup and run instructions. | A new project user can follow the README to install dependencies, initialize data, run, and test the app. |
| NFR-08 | Performance targets shall be agreed before implementation if the demonstration has response-time or concurrency expectations. | Target not yet specified; see stakeholder questions. |
| NFR-09 | The system shall be maintainable using the selected stack without requiring a hosted service for the basic demonstration. | MVP core flow works locally; any optional external dependency is separately approved and documented. |

## 5. Security and privacy requirements

| ID | Requirement | Priority / status |
|---|---|---|
| SEC-01 | The system shall not use real student or company data in development, tests, or the demonstration. | Must |
| SEC-02 | The system shall validate all external input at the application boundary, including type, presence, and configured size limits. | Must |
| SEC-03 | Authorization shall be enforced in application code for any protected operation; prompts or model instructions shall not be treated as access control. | Must |
| SEC-04 | The MVP shall expose only narrowly scoped, read-only tools or data access to answer questions. | Must |
| SEC-05 | Retrieved knowledge-base content shall be treated as untrusted input. Instructions in content shall not change system behavior, authorization, or output rules. | Must |
| SEC-06 | Secrets, credentials, hidden prompts, and internal implementation details shall not be disclosed to users or committed to source control. | Must |
| SEC-07 | The system shall not collect or retain personal information unless the college approves the purpose, data fields, access, and retention period. | Must |
| SEC-08 | Errors and logs shall not include secrets, full sensitive content, or unnecessary personal data. | Must; logging/retention design TBD |
| SEC-09 | If an external model or service is proposed, the project shall document what data leaves the application and obtain approval before sending user questions or source content to it. | Conditional; model/provider TBD |
| SEC-10 | Knowledge content shall have an identifiable owner and approval status before it is presented as authoritative. | Must; ownership workflow TBD |

## 6. Assumptions

1. The initial demonstration is local or otherwise limited in audience; public production deployment is not currently required.
2. The initial knowledge base can be small, curated, and composed of fictional or explicitly approved non-sensitive college information.
3. Questions are general information requests, not requests to retrieve individual student records.
4. The first release does not need to modify college records or perform transactions.
5. The project will use Python 3, FastAPI, SQLite, HTML/CSS/JavaScript, and pytest.
6. College stakeholders will identify and approve the sources and content that the assistant may use.
7. Retrieval and response rules can be implemented separately from any model, and the demo should continue to behave safely if a model is absent or unavailable.

These assumptions are provisional and must be confirmed before building functionality that depends on them.

## 7. Constraints

- Use the specified lightweight stack; do not add unnecessary frameworks or cloud services.
- Keep the demo understandable for a B.Tech Software Engineering lecture.
- Do not use real student or company data.
- Do not invent college policies or imply unsupported information is official.
- Keep transactional truth in SQLite.
- Enforce authorization in application code, not solely through prompts.
- Keep any tools read-only and narrowly scoped.
- No application code is specified by this document; implementation requires stakeholder decisions where marked TBD.

## 8. Use cases

### UC-01 — Ask a question with an available answer

**Primary actor:** Student or demonstration user  
**Preconditions:** The application is available and approved knowledge content is configured.  
**Main flow:**
1. The user enters a question.
2. The system validates the input.
3. The system searches the configured knowledge sources.
4. The system presents a supported answer and its source.
5. The user reviews the answer and source.
**Postcondition:** No college record has been changed.
**Alternate flow:** If the input is invalid, the system explains the validation issue and allows the user to try again.

### UC-02 — Ask a question not covered by the sources

**Primary actor:** Student or demonstration user  
**Preconditions:** The application is available.
**Main flow:**
1. The user enters a question.
2. The system validates the input and searches approved sources.
3. The system cannot find sufficient supporting information.
4. The system states that the source does not provide enough information.
**Postcondition:** No unsupported policy or factual answer is presented.

### UC-03 — Maintain approved knowledge content

**Primary actor:** Authorized content owner or maintainer  
**Preconditions:** The person has been authorized through the agreed maintenance process.
**Main flow:**
1. The content owner supplies or updates a source.
2. The source is reviewed and approved according to the college's agreed process.
3. An authorized maintainer updates the configured knowledge base.
4. The change is checked to ensure the content and source attribution are available to retrieval.
**Postcondition:** Only approved content is eligible for responses.
**Open decision:** The MVP may use a checked-in local file or another simple process; no administrative UI is assumed.

## 9. User stories

| ID | User story | Related requirements |
|---|---|---|
| US-01 | As a student, I want to ask a question in ordinary language so that I can find relevant approved college information. | FR-01, FR-02, FR-03 |
| US-02 | As a student, I want to see where an answer came from so that I can verify it. | FR-04, FR-06, FR-11 |
| US-03 | As a student, I want the assistant to say when information is unavailable so that it does not mislead me. | FR-05, FR-09 |
| US-04 | As a content owner, I want answers based only on approved material so that the assistant does not invent or misstate college policy. | FR-03, FR-04, FR-07, SEC-05, SEC-10 |
| US-05 | As a maintainer, I want a documented way to update knowledge content so that answers can reflect approved changes. | FR-10, SEC-10 |
| US-06 | As a college stakeholder, I want the demonstration to avoid personal data and record-changing actions so that its risks remain limited. | FR-08, SEC-01, SEC-04, SEC-07 |
| US-07 | As a lecturer, I want the system and tests to use a simple, local stack so that the design can be explained and reproduced in class. | NFR-01, NFR-03, NFR-04, NFR-07 |

## 10. Acceptance criteria

### AC-01 — Submit a question (FR-01, FR-02)

**Given** the application is available  
**When** a user submits a non-empty question within the configured input limit  
**Then** the system processes it and displays the resulting answer state.

### AC-02 — Reject invalid input (FR-02, FR-09, SEC-02)

**Given** the application is available  
**When** a user submits an empty, whitespace-only, malformed, or over-limit question  
**Then** the system rejects it with a clear validation message and does not search or answer it.

### AC-03 — Answer from an approved source (FR-03, FR-04, FR-06)

**Given** an approved source contains sufficient information to answer a question  
**When** the user submits that question  
**Then** the answer is supported by that source and the user can identify the source.

### AC-04 — Insufficient evidence (FR-05)

**Given** no configured approved source contains sufficient information  
**When** the user submits the question  
**Then** the assistant says that the source does not provide enough information and does not guess.

### AC-05 — Ignore instructions inside retrieved content (FR-07, SEC-05)

**Given** a retrieved source contains text instructing the assistant to ignore its rules, reveal internal information, or perform an action  
**When** the system processes a question that retrieves that source  
**Then** the text is treated only as untrusted source content and does not override the system's behavior or security rules.

### AC-06 — No record-changing operation (FR-08, SEC-04)

**Given** a user asks the assistant to change, submit, or delete a college record  
**When** the system handles the request  
**Then** it does not perform the change and does not invoke a write-capable tool.

### AC-07 — Safe error handling (FR-09, SEC-06, SEC-08)

**Given** an internal processing failure occurs  
**When** the system returns an error to the user  
**Then** the response is understandable and does not expose secrets, hidden prompts, stack traces, or unnecessary personal data.

### AC-08 — Approved content updates (FR-10, SEC-10)

**Given** a content owner has approved a source and the maintainer is authorized  
**When** the maintainer follows the documented update process  
**Then** the source becomes available to retrieval with its attribution, and unapproved content is not represented as authoritative.

### AC-09 — No unapproved personal data collection (SEC-01, SEC-07)

**Given** no data collection and retention purpose has been approved  
**When** users interact with the MVP  
**Then** the application does not persist identifiable user questions or personal records.

### AC-10 — Local reproducibility (NFR-01, NFR-03, NFR-04, NFR-07)

**Given** a developer has the documented prerequisites  
**When** they follow the setup instructions  
**Then** they can run the application and pytest suite locally without real student/company data or a hosted cloud service.

## 11. Edge cases

| ID | Scenario | Required behavior |
|---|---|---|
| EDGE-01 | Empty or whitespace-only question | Reject with validation feedback; do not retrieve. |
| EDGE-02 | Question exceeds the configured maximum size | Reject or request a shorter question; do not truncate silently. |
| EDGE-03 | Unsupported language, ambiguous wording, or multiple questions in one input | Ask for clarification or state that the source lacks enough information; do not guess. Supported languages TBD. |
| EDGE-04 | Relevant source exists but is incomplete, contradictory, or stale | Do not resolve conflicts by invention; report the limitation or request stakeholder-defined conflict handling. |
| EDGE-05 | Retrieved document includes prompt-injection-like instructions | Treat as untrusted content and follow system rules. |
| EDGE-06 | No sources are configured, or all sources fail to load | Return the insufficient-information or service-unavailable state clearly; do not fabricate an answer. |
| EDGE-07 | A source has no usable title, link, or attribution | Do not present it as a properly cited authoritative source; surface a safe limitation for maintainers. |
| EDGE-08 | Duplicate or near-duplicate source material | Avoid presenting duplicate citations as separate corroboration; exact deduplication behavior TBD. |
| EDGE-09 | User requests private student-specific information | Do not retrieve or disclose it in the MVP; direct the user to an approved official channel if that wording is agreed. |
| EDGE-10 | User asks for an action such as enrollment, fee payment, or record correction | Explain that the demonstration cannot perform transactions. |
| EDGE-11 | SQLite or another local dependency is unavailable or locked | Return a clear failure state; do not claim success or silently substitute unsaved data. |
| EDGE-12 | Very rapid repeated requests or unusually large traffic | Apply agreed resource limits if required; numeric thresholds TBD. |

## 12. Traceability summary

| Requirement group | IDs | Primary validation |
|---|---|---|
| User interaction and answering | FR-01–FR-06, FR-09, FR-11–FR-12 | API and service tests; manual browser check |
| Content safety and tools | FR-07–FR-08, SEC-04–SEC-05 | Tests with instruction-like source text; verify no write-capable integration |
| Knowledge maintenance | FR-10, SEC-10 | Process review and tests for configured source attribution |
| Quality and operation | NFR-01–NFR-09 | Code review, pytest, and local setup/run verification |
| Privacy and security | SEC-01–SEC-10 | Synthetic test fixtures, input/security tests, and data-flow review |

## 13. Stakeholder questions before implementation

These questions must be answered or explicitly deferred before the affected requirements are implemented. The proposed defaults below are recommendations for keeping the demonstration small, not confirmed college policy.

1. **Audience and deployment:** Who may use the MVP, and will it run only locally in a classroom or be reachable on a college network?  
   *Recommended default:* local classroom demonstration only.
2. **Supported subject matter:** Which topics may it answer (for example, fictional demo FAQs, public campus information, or actual approved policies), and which topics must it refuse?  
   *Required:* provide a bounded topic list and approved sample sources.
3. **Source authority and ownership:** Who approves source material, who maintains it, and how will the system identify an authoritative/current source?  
   *Required:* name a content owner and agree on source attribution and review process.
4. **Knowledge-base format:** Should the first version use a small checked-in JSON/Markdown file, SQLite records, or another format?  
   *Recommended default:* a small local, version-controlled dataset for FAQ content; use SQLite for transactional data only if the MVP introduces it.
5. **Meaning of “AI”:** Is deterministic retrieval sufficient for the classroom demonstration, or is an LLM required? If required, which model/provider and what approval is needed?  
   *Recommended default:* begin with local deterministic retrieval; do not transmit questions or source documents externally.
6. **Citation behavior:** What must a citation show (title, section, URL, publication date, excerpt), and may a user open the original source?  
   *Recommended default:* source title and relevant section or link, where available.
7. **Unsupported/conflicting answers:** What precise wording should be used for missing, ambiguous, stale, or contradictory information? Should the system ask a follow-up question?  
   *Recommended default:* clearly state insufficient source information; never guess.
8. **User identity and authorization:** Is login required? Are any sources restricted by role, or is all MVP content public to the demo audience?  
   *Recommended default:* no login only if the knowledge base contains public/general content and there are no protected operations; otherwise define roles and enforce authorization in application code.
9. **Data retention and logs:** Should questions or responses be stored? If so, for what purpose, which fields, who may access them, and for how long?  
   *Recommended default:* do not persist identifiable questions; avoid logging request bodies.
10. **Privacy notice and disclaimer:** What notice, disclaimer, or official-channel referral should users see, and who approves its wording?
11. **Language and accessibility:** Which languages must be supported? Are there accessibility, mobile-browser, or assistive-technology requirements?
12. **Input and abuse limits:** What maximum question length, request rate, and concurrent usage should be supported?  
   *Recommended default:* set conservative limits appropriate to one classroom after expected usage is known.
13. **Operational targets:** What response-time, availability, and recovery expectations apply, if any?  
   *Recommended default:* no production SLA for a local demonstration.
14. **Knowledge updates:** Who may change the knowledge base, how are changes reviewed, and should changes take effect immediately or only after a release?
15. **Data store responsibilities:** What transactional data, if any, must SQLite hold in the MVP?  
   *Recommended default:* none unless a confirmed use case requires it; do not store conversational history by default.

## 14. Readiness / exit criteria

Implementation planning may proceed when stakeholders have, at minimum:

- Confirmed audience and deployment context.
- Approved the topic boundaries and provided non-sensitive sample knowledge content.
- Named a source owner and agreed how sources are attributed and updated.
- Decided whether an LLM is actually required and approved its data flow, if applicable.
- Decided whether identity, persistence, logs, and retention are needed.
- Confirmed user-facing fallback/disclaimer wording and any essential language/accessibility expectations.
