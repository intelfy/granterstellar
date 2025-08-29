Archived on 2025-08-28 — replaced by concise AI endpoints overview in `.github/copilot-instructions.md` and API stubs in `api/ai/views.py`.

Original content retained for reference below.

---

agent_flow.md

Note: This is a conceptual overview for the authoring agents. For actual API contracts, see `api/ai/views.py` and the quick references in `.github/copilot-instructions.md`.

AGENTS:
1. Planner
2. Writer
3. Formatter

QUIZ FLOW:
1. User inputs URL to the grant call they want to write a proposal for.
2. PLANNER agent reviews the call for information required, checks if a corresponding template exists in the RAG, determines which sections are required, in what order, and what questions to ask the user to extract the information.
3. Quiz begins with first question and input field determined by PLANNER. User inputs text or uploads files.
4. WRITER agent parses user inputs (reading text, OCR on files) and writes corresponding section of the proposal.
5. Quiz presents the WRITER agent's draft to the user for approval/edits. User asks to have a few changes made.
6. WRITER agent revisits draft, implementing requested changes from user.
7. Quiz presents the WRITER agent's new draft to the user. The user approves.
8. Quiz loads next question determined by PLANNER for the next section. User again inputs information and uploads files.
9. WRITER agent parses user inputs, drafting next section before quiz presents that for review.
10. When all sections are written and approved, PLANNER agent confirms that the task is complete. FORMATTER agent then begins formatting.
11. First, FORMATTER agent checks RAG for existing templates or sample proposals from the same grant call, preferring to format current proposal identically.
12. If no templates or sample proposals exist, FORMATTER uses inference and reviews similar proposal calls to determine how to best structure grant proposal.
13. User is displayed formatted final version of proposal in simulated .PDF view and asked to approve.
14. When user approves, they are asked if they would like to immediately export the file and in which format.
15. Proposal is saved to user's profile, and accessible via "My Proposals" on profile page.
