Archived on 2025-08-28 — superseded by README.md (overview) and docs/install_guide.md (deployment). Kept for historical context.

Note: This is the product vision narrative. For implementation details and current status, see README.md and docs/install_guide.md.

We are building a simple web app to help people apply for grants. We are naming it Granterstellar. We are primarily targeting non-profits and small businesses applying for, for example, Horizon 2020 EU grants.

The software will be subscription-based with a very limited free tier. The idea is to have a fully guided writing process for users. Our form asks a few questions for each section, the user provides their answers (or uploads corresponding files), and our AI prints the specific section for review. The user will then either approve or ask for changes to the section, those will be made, and we then progress to the next section.

When we are done (or any time before then), the user has the option to download their file as an .md file, a .docx, or a .pdf, which they can then submit as their grant proposal.

The flow will look like this:
(PLEASE REVIEW AGENT_FLOW.md FOR A MORE TECHNICAL EXPLANATION)
- The user opens the app and is asked to input a link to or the specifications of the grant they're applying for. Our AI will parse this information and determine how to structure the grant proposal accordingly
- The AI will now walk the user through a step-by-step process according to its predetermined structure, taking one section at a time and ensuring the user is happy with it before moving on.
- At every step of the way, the document is saved, so the user can resume their session at a later time should they want to.
- The AI will support simple multimodal generation, such as flow charts or images. It will also allow the user to upload their own content to be included in the grant proposal.
- For free users, they will only be given a single of these proposal completions for free. For paid users, they will be given X amount per month (we will determine this depending on what is economically viable)
