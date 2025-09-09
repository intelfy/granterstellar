Archived on 2025-08-28 — superseded by .github/copilot-instructions.md (contributor guide), README.md (overview), and docs/install_guide.md (deployment).

This file contains the previous long-form technical specification for Granterstellar. Refer to the above files for accurate, up-to-date guidance.

# Granterstellar: Technical Specification & Architectural Blueprint (Archived)

Status: Archived for historical context. The authoritative, concise repo guidance now lives in:
- .github/copilot-instructions.md (architecture and conventions for contributors/agents)
- docs/install_guide.md (deployment and environment variables)
- README.md (top-level quickstart and dev notes)

This document remains as a reference but may contain outdated suggestions (e.g., alternative export engines, landing-focused topology). Prefer the files listed above when in doubt.

An archived pointer copy also exists at `docs/archive/technical_spec_archived.md`.

This document serves as a comprehensive technical specification for the Granterstellar application, translating the product vision into a detailed, actionable blueprint for the engineering team. It outlines the core architectural choices, data management strategies, and implementation details for each key feature, all while adhering to the user's explicit requirements for a secure, self-hosted, open-source platform with a mobile-first design.

## **1\. Executive Summary**

Granterstellar is a self-hosted SaaS platform designed to streamline the grant proposal process through guided writing, research, and tracking. The application will leverage a modern, open-source technology stack to ensure security, performance, and complete data ownership for our users, which is a key priority for handling sensitive grant-related information. The proposed architecture is a containerized monolithic system, with a clear separation between a robust backend API and a dynamic front-end application. This approach provides the simplicity of a single codebase for self-hosting while allowing for independent scaling and development of the user-facing and server-side components.
The core technology stack has been selected to meet the project's unique requirements. Python with the Django framework will form the backend, prized for its out-of-the-box security features and rapid development capabilities. The front-end will be built with React, ensuring a responsive, mobile-first design that handles complex user interactions and state management with efficiency. PostgreSQL is the chosen database, specifically for its ability to combine transactional integrity with the schema flexibility of the JSONB data type, which is perfectly suited for managing the dynamic structure of grant proposals. For the user interface, SurveyJS is recommended as a self-hostable, JSON-driven form builder that supports complex, stateful workflows. AI functionalities will be powered by a hybrid model, potentially integrating a third-party API like GPT-5 for advanced reasoning tasks while considering a self-hosted, lightweight model for simpler operations to manage costs and data privacy. Finally, the entire application will be containerized using Docker and Docker Compose, ensuring a standardized, portable, and easily reproducible deployment on self-hosted Linux servers.
The blueprint is built upon three critical strategic pillars that are essential for the application's success. First, a **Hybrid Data Strategy** combines the transactional integrity of a relational database with the schema flexibility of JSONB to handle both structured user data and dynamic proposal content. Second, a **Multi-Layered Security Model** is implemented at every level, from user authentication (OAuth) and data access (PostgreSQL RLS) to input sanitization (Prompt Injection Prevention) and API key management. Third, a **Monetization through Usage** strategy proposes a freemium model that ties user value directly to the cost of AI API calls, creating a clear and compelling upgrade path for users as their needs evolve.

## **2\. Granterstellar System Architecture**

### **Architectural Vision: Monolith with Service Separation**

The chosen architectural vision for Granterstellar is a containerized monolith. This approach is optimal for a project that prioritizes self-hosting and full data control. Unlike a complex microservices architecture, a monolith simplifies deployment, management, and debugging, as all core services and business logic reside within a single codebase. The user has specified that the application itself will not be distributed or open source but will be deployed as a SaaS solution on self-hosted servers. The use of Docker and Docker Compose is therefore purely for internal development and operational efficiency, standardizing the environment and simplifying the deployment process on our Linux servers.
The system will be composed of two primary, independently developed components. The backend, built with the Django framework, will serve as the central API layer. It will handle all critical business logic, including user authentication, data persistence, and communication with third-party services. The frontend, a single-page application (SPA) developed with React, will consume these APIs to provide a rich, interactive user interface. This separation of concerns ensures that the user interface can evolve and scale independently from the server-side logic, without the complexity of a fully distributed system. The communication between the two layers will be handled via a RESTful API, providing a clean contract that facilitates parallel development and a more maintainable codebase. In deployment, Coolify manages a Traefik reverse proxy as the entry point, routing requests to the appropriate containers and handling TLS certificates; locally, Docker Compose can be used without an explicit proxy service.

### **Technology Stack Summary**

The following table provides a definitive list of all recommended software, frameworks, and tools. Each choice is justified based on its alignment with the project's core requirements: open-source, self-hosted, secure, and mobile-first.

| Component | Recommended Technology | Description | Justification |
| :---- | :---- | :---- | :---- |
| **Backend** | Django (Python) | A high-level Python web framework that encourages rapid development and clean, pragmatic design. | Offers a complete backend ecosystem with built-in features for user authentication, security against common attacks (SQL injection, XSS), and an ORM, which streamlines development. Its robust community provides excellent support and security patches. |
| **Frontend** | React (JavaScript) | A JavaScript library for building user interfaces with a component-based architecture and a virtual DOM. | Ideal for creating a complex, interactive, and mobile-first UI. Its one-way data flow simplifies debugging and state management, which is critical for a form-heavy application. |
| **Database** | PostgreSQL | A powerful, open-source object-relational database system with advanced features, including JSONB. | Provides strong data consistency and transactional integrity (ACID) for user and subscription data, which is non-negotiable. JSONB support allows for the flexible storage and high-performance querying of semi-structured proposal content within a single database. |
| **Forms** | SurveyJS | An open-source, self-hostable JavaScript form builder that generates JSON schemas. | This no-code, drag-and-drop tool perfectly complements the JSONB data model, allowing non-technical users to create dynamic forms that are easily consumed and stored by the backend. |
| **AI** | Gemini/GPT-5 (Paid API) & Open-Source (Local) | A hybrid approach using a high-performance, third-party LLM for complex tasks and a self-hosted, lightweight model for simpler, low-cost operations. | This strategy balances the need for cutting-edge generative AI capabilities with the long-term goal of cost management and data privacy. It leverages the strengths of each model type for different use cases. |
| **Payments** | Stripe | A widely used, secure payment gateway that specializes in managing recurring payments for SaaS. | Its robust API simplifies the implementation of the subscription system, and its comprehensive features, like fraud prevention and support for multiple currencies, are ideal for a globally accessible application. |
| **Deployment** | Docker & Docker Compose | A containerization platform and a tool for defining and running multi-container applications. | Standardizes the environment for development, testing, and production. Docker Compose simplifies the entire self-hosting process, bundling all dependencies and configurations into a portable and reproducible package that runs on Linux. |

## **3\. Data Model & Management**

### **Database Selection: A Hybrid PostgreSQL Model**

The choice of database is a foundational decision that will dictate the application's long-term flexibility and performance. The user's query describes an application that handles two distinct types of data. First, there is structured, relational data, such as user accounts, subscription plans, and the details of available grants. This information requires the strict consistency and transactional integrity that relational databases like PostgreSQL are known for. Second, there is the dynamic, user-generated content of the grant proposals themselves, which can vary in structure from one user to the next.
A purely relational (SQL) database would struggle with the flexible schema required for the proposal content, leading to a rigid and brittle design that is difficult to update. Conversely, a purely non-relational (NoSQL) database, while excellent for unstructured data, might not provide the ACID compliance necessary for critical transactional data like user payments and subscriptions.
This technical challenge is addressed by adopting a hybrid approach with **PostgreSQL**. PostgreSQL is a powerful relational database that also offers first-class support for JSONB, a binary format for storing JSON data. This solution allows the application to leverage the core strengths of a relational model for structured data while seamlessly accommodating the dynamic, user-defined fields of the grant proposals. This is a crucial point of synergy, as the choice of a stateful, JSON-driven form builder like SurveyJS on the frontend is directly supported by the backend's JSONB data model. The system will be able to store the exact JSON payload from the user's form submission in a JSONB column, avoiding the need for complex and inefficient data transformations.

### **Logical Data Model**

The core data model for Granterstellar will be relational, with tables designed to ensure data integrity and strong relationships between entities. Key tables will include Users, Organizations, Grants, Proposals, and Subscriptions. Foreign keys will establish clear connections, for instance, a User will be linked to their Organization, and a Proposal will be linked to the User who created it and the Grant it targets.
For the dynamic content of the proposals, a single JSONB column will be included in the Proposals table. This column will hold the entire, semi-structured JSON object that represents the user's filled-out form. This design is highly efficient for both storage and retrieval. JSONB stores data in a decomposed binary format, which reduces storage size and enables faster querying compared to storing raw JSON text. PostgreSQL also allows for indexing on JSONB columns, which significantly improves query performance for fields within the JSON data.

#### **Proposal Data Format (JSONB Example)**

The following is an example of a grant proposal's data structure as it would be stored in the JSONB column of the Proposals table. This format accommodates the free-form and nested nature of a typical grant application.
`{`
  `"proposalId": "GSTR-2024-001-A",`
  `"grantId": "GRT-12345-USA",`
  `"version": 1,`
  `"lastSaved": "2024-11-20T14:30:00Z",`
  `"sections": {`
    `"executiveSummary": {`
      `"title": "Executive Summary",`
      `"content": "This proposal outlines our plan to..."`
    `},`
    `"projectNarrative": {`
      `"title": "Project Narrative",`
      `"description": "Please describe the project in detail.",`
      `"content": "The project will be executed in three phases..."`
    `},`
    `"budget": {`
      `"title": "Budget Breakdown",`
      `"items":,`
      `"total": 65000`
    `},`
    `"references":`
  `},`
  `"metadata": {`
    `"tags":,`
    `"reviewStatus": "draft",`
    `"notes": "Follow up with Dr. Smith regarding budget."`
  `}`
`}`

This nested structure can be efficiently queried using PostgreSQL's JSONB operators. For example, to retrieve the total budget from a specific proposal, one would use the \-\> and \-\>\> operators to navigate the object path. To search for all proposals with a specific tag, the @\> operator can be used, which checks for containment within the JSONB object. This demonstrates the power and flexibility of this data model.

### **Data Security: PostgreSQL Row-Level Security (RLS)**

A paramount concern for any application handling sensitive user data is ensuring that one user cannot access another user's information. The user has specified a critical need for security. Beyond application-level security, a robust solution must enforce data access controls at the database layer itself. For this, PostgreSQL's Row-Level Security (RLS) feature is the ideal mechanism.
Based on the new requirements, the RLS policies will be more granular to support different access levels within an organization. The core principle of RLS remains the same: it applies a filter before any user query is executed, ensuring a "secure-by-default" data layer that protects against accidental data leaks. The system will use two primary RLS policies on the Proposals table to implement the required access control:

1. **Organizational Access for Admins**: This policy will permit users with the admin role within an organization to view all proposals belonging to that organization. This is achieved by joining the Proposals table to the Users and Organizations tables and checking if the user's role is admin within the context of the organization. This provides the desired oversight for leadership roles without compromising data isolation between different organizations.
2. **Individual & Shared Access for Users**: This policy will allow a standard user to view their own proposals and any proposals that have been explicitly shared with them. This can be implemented with a USING clause that checks two conditions: proposal.user\_id \= current\_user\_id OR proposal.id is in a list of shared\_proposal\_ids for that user. Multiple policies can be combined with OR or AND logic to build these complex access rules.

The implementation will involve creating a custom function to determine the current user's role and organization ID, which will be set as session variables upon login. This allows the RLS policies to be dynamic and context-aware. This multi-layered approach to security provides peace of mind and ensures compliance with data protection regulations, an essential consideration for a self-hosted platform.

## **4\. Core Application Feature Specifications**

### **Technical Implementation: The Stateful Front-end**

The user journey for grant proposal writing is a stateful and complex process, requiring a front-end that can handle multi-step forms, conditional logic, and real-time updates without a full page reload. The choice of the front-end framework and form builder is crucial to a seamless user experience.
React is the recommended framework for the front-end. Its component-based architecture is perfectly suited for building the modular, interactive UI of Granterstellar. Components can be created for each section of a grant proposal (e.g., ExecutiveSummary, BudgetNarrative), and these reusable components can be easily integrated into the main form. React's virtual DOM also ensures high performance by optimizing UI updates, which is essential for a fluid, mobile-first experience.
The form builder that will power the application is SurveyJS. It is a powerful, open-source JavaScript library that provides a drag-and-drop UI for form creation. Crucially, SurveyJS is "server- and database-agnostic," which aligns with the self-hosting requirement and gives the application full control over data ownership. The form builder automatically generates a JSON schema for the form's structure, which is stored on the backend. When a user interacts with the form, the front-end manages the form's state in real-time. Upon submission, a single JSON object containing the user's responses is sent to the backend, where it is stored in the JSONB database column. This seamless workflow, from a no-code UI on the front-end to a flexible data model on the back-end, is a core strength of this architectural approach.

### **Technical Implementation: The AI-Powered Backend**

The AI model is a core component of the Granterstellar value proposition, enabling guided writing and research. The system will leverage a hybrid model to balance cost, performance, and functionality.
The AI workflow is a core business process, not a simple "assist." The user will be guided through a series of questions for each section of a grant. The AI will then take the user's plain text input and file uploads and, in a single, comprehensive action, synthesize this information into a fully drafted grant section. The user is then presented with the completed section for review and approval before moving to the next part of the proposal.
This multi-step, generative process requires an AI model with strong reasoning and multi-modal capabilities. For advanced tasks, such as summarizing long, complex grant documents or generating detailed proposal narratives, a paid, third-party API from a major provider like Google's Gemini or OpenAI's GPT-5 is recommended. These models can process text, images, and audio in a single API call, making them ideal for the multi-modal workflow. For simpler, more contained tasks, a self-hosted, lightweight open-source model could be considered to reduce costs and maintain data privacy for sensitive prompts.

#### **Multimodal Input and Diagram Generation**

To handle the user's input, which may include plain text, PDFs, and image files, the backend will require robust processing pipelines.

* **Document and Image Parsing**: For file uploads, a combination of text parsing and Optical Character Recognition (OCR) will be used. Python libraries like Pytesseract and OCRmyPDF are excellent open-source choices for this task. Pytesseract is a Python wrapper for the Tesseract-OCR engine, which is maintained by Google and known for its accuracy in deciphering text from images and scanned documents in over 100 languages. For PDFs, OCRmyPDF can rasterize each page into an image and then perform OCR to generate a searchable text layer, which can be extracted for the AI model's use.
* **Diagram Generation**: The user has requested the ability to generate diagrams and flowcharts. The AI must be able to interpret a request from the user (e.g., "create a flowchart of our workflow") and generate a diagram based on the provided information. This can be achieved in two ways:
  1. **API Integration**: Platforms like Miro and Eraser offer AI-powered diagram generation from natural language prompts. The Granterstellar backend would send a prompt to their API and receive a diagram image or a code-based diagram definition in return. This approach is powerful but adds a dependency on a third-party service.
  2. **Self-Hosted Libraries**: To maintain full control and ownership, open-source libraries that support "Diagrams as Code" could be used. Libraries like Kroki or Diagrams can be self-hosted and provide an API that takes a text-based description (e.g., Mermaid, PlantUML syntax) and generates an image (SVG, PNG, etc.). The AI would first generate the diagram code, which the application would then render.

A significant risk with integrating AI models is prompt injection, where an attacker crafts a malicious prompt to manipulate the model's behavior. This can lead to data exfiltration or unauthorized actions. The blueprint will employ a multi-layered defense strategy to mitigate this risk. First, all user input will be validated and sanitized on the backend before being sent to the AI API. Second, a specialized open-source library like Promptfoo or Rebuff will be used as a "prompt shield". This dedicated classifier will analyze incoming prompts for adversarial intent and block them *before* they can interact with the main AI model, providing a crucial layer of defense. Finally, the principle of least privilege will be applied, ensuring that the AI API is only granted the minimum permissions necessary to perform its task, which limits the potential damage of a successful attack.

### **Technical Implementation: Subscription & Payment System**

The business model for Granterstellar is based on a freemium offering that incentivizes users to upgrade from a free to a paid subscription. A simplified model is proposed that is tied directly to the core value proposition: AI-powered proposal generation.

* **Free Tier**: Users are granted one free grant proposal. This allows them to experience the full, end-to-end value of the platform without a financial commitment. Once they have completed and downloaded this proposal, they will hit a paywall and be prompted to upgrade.
* **Premium Tier**: Users on a premium plan receive a fixed number of proposals per month, with the exact number to be determined by the business. The user suggested 5-10 proposals. This model provides a predictable cost for the user while ensuring our service remains profitable.
* **Overages**: If a premium user exceeds their monthly proposal limit, they will be given the option to purchase "bundles" of additional proposals for a one-time fee. This provides a flexible monetization path for power users who have high-volume needs.
* **Enterprise Tier**: For large organizations with a significant number of users or high-volume needs, a custom, contact-based plan will be offered. This allows for a tailored solution that meets their specific requirements and secures a higher-value contract.

The subscription and payment system will be managed by a third-party payment gateway that is well-suited for SaaS applications. Stripe is the top recommendation for this purpose. It provides a robust API for handling recurring payments, secure transactions (PCI DSS compliance), and fraud prevention. The implementation will include a comprehensive subscription lifecycle management system that automates upgrades, downgrades, and cancellations with proration logic. A self-service customer portal will also be provided, empowering users to manage their plans and billing information, which reduces the support burden and enhances user satisfaction.

## **5\. Security Posture & Best Practices**

The security of Granterstellar is a critical consideration, especially given its focus on user data and self-hosting. A multi-layered approach will be implemented to address potential vulnerabilities at every stage, from user authentication to data storage.

### **Access Control**

User authentication will be handled by a third-party OAuth provider. This is a critical security decision, as it offloads the complex and high-risk task of password management and security to a dedicated, expert service. The application will use a secure token (e.g., JWT) provided by the OAuth provider to establish user identity, ensuring that our system never handles or stores sensitive user credentials. This adheres to the principle of least privilege, as the application only receives the necessary information to identify the user and manage their session.

### **Data Privacy**

As previously detailed, PostgreSQL's Row-Level Security (RLS) is a fundamental component of the security posture. It acts as a non-bypassable final guarantee that user data remains isolated and protected, even if a vulnerability were to exist at the application layer. This ensures that users can only access the rows of data that belong to them, which is a key requirement for a multi-tenant SaaS application.

### **Server-Side Security**

The self-hosted nature of Granterstellar places the responsibility of server security on the platform. The application will be deployed on a Linux server using Docker, which provides an isolated and standardized environment. The deployment workflow will include best practices for hardening the server and containers. This includes regularly updating all software, limiting exposed ports, and configuring robust logging to track and review user and system activities for unusual behavior or potential breaches.

### **API Key Management**

All API keys for third-party services (AI, OAuth, Payments) will be stored in environment variables, not committed to the source code. This prevents credentials from being accidentally exposed in public repositories. For a higher security posture, a dedicated secrets management tool could be integrated to securely store and rotate keys, further minimizing the risk of a compromised credential.

## **6\. Deployment & Operations**

### **Containerization with Docker Compose**

The user's requirement for self-hosting on Linux servers makes containerization with Docker and Docker Compose the ideal solution. Docker simplifies the entire deployment process by packaging the application, its dependencies, and its configuration into a single, portable unit called a container. This eliminates the "it works on my machine" problem and ensures that the application will run consistently across all environments.
 Docker Compose, in turn, simplifies the management of the multi-container application. A single docker-compose.yml file will define all the services—the front-end, the back-end, and the database—and their interconnections. In Coolify, Traefik is provided and configured by the platform (via UI or labels), so we do not run our own reverse proxy container. With a single command locally (or via Coolify’s deploy), the entire stack can be built and deployed, which dramatically reduces the complexity of self-hosting for the end user.

### **Coolify + Traefik topology (deployment options)**

There are two workable ways to publish the app behind Coolify-managed Traefik while keeping the codebase separation of concerns:

1) Single-application deployment (recommended for MVP)
- Build the React SPA to static assets during CI and bundle them into the Django image (served via WhiteNoise or Django static files).
- Traefik routes the root domain to the Django service; the API lives at /api under the same container (no cross-origin, simpler cookies and headers).
- Pros: One Coolify app, fewer moving parts, simpler TLS and headers, no path-based routing config. Cons: Tight coupling at deploy time; SPA rebuild needed for API redeploys (mitigated by CI caching and multi-stage builds).

2) Dual-application deployment (SPA + API)
- Two Coolify apps share the same domain with path-based routing: Host(`app.example.com`) → SPA, and Host(`app.example.com`) && PathPrefix(`/api`) → API.
- Pros: Independent deploy cadence and scaling. Cons: Path-based router rules to maintain; CORS and cookies require careful configuration; more moving parts.

Either topology maintains the architectural split in code. For early testers, prefer option 1 to minimize operational complexity; revisit option 2 when traffic or org structure requires independent scaling.

### **Backup and Disaster Recovery**

A critical component of any production system is a robust backup strategy. Given the sensitive nature of the data, the solution must include a secure, encrypted backup process. **Duplicati** is an excellent open-source choice that fits the project's requirements for a self-hosted, secure, and reliable backup solution.
Duplicati is a backup client that can store encrypted, incremental, and compressed backups to a variety of cloud storage services. Its key features align perfectly with the user's needs:

* **Strong Encryption**: Duplicati uses AES-256 encryption to protect backups, with the password/key never leaving the user's machine. The spec sheet will detail how to configure this with a dedicated environment variable to ensure the encryption key is not stored in plain text.
* **Incremental Backups & Deduplication**: After the initial full backup, Duplicati only backs up the changed data, saving time and storage space. It also deduplicates data blocks, storing identical content only once, which is highly efficient for documents with similar content.
* **Docker Integration**: Duplicati provides an official Docker image, making it easy to integrate into the existing Docker Compose setup. A dedicated container will be configured to handle backups, with the host directories containing the user data mounted into the container using the \-v option. This setup ensures the configuration is preserved between container restarts by mounting a volume at the /data path.

This setup provides a fully automated, encrypted, and efficient backup solution that can be configured to send data to the client's preferred cloud storage provider.

### **Deployment Workflow**

The deployment workflow will be a simple, two-step process using Docker Compose.

1. **Build and Run**: The user will execute the docker compose up \--build command. This will automatically download all necessary base images, build the custom application containers based on the provided Dockerfiles, and start all services in the correct order.
2. **Management**: The user can then use simple docker compose commands to manage the application, such as docker compose down to stop all services, or docker compose logs \<service-name\> to view logs for a specific container in real-time. This provides a streamlined and user-friendly operational experience.

## **7\. User Journey & Technical Touchpoints**

To ensure a seamless experience for grant writers, the application's technical flow must be meticulously aligned with the user journey. The following table provides a breakdown of a user's key actions and the corresponding system-level responses, showcasing the interplay between the front-end, back-end, and database.

| User Journey Stage | User Action | Front-end/Client-side Action | Backend Action | Database Action |
| :---- | :---- | :---- | :---- | :---- |
| **New Proposal Creation** | Clicks "Start My Proposal" | Sends a GET request to api/form\_schema. Initializes a new, empty form state. | Fetches the default JSON schema for a grant proposal from a configuration store. Responds with the JSON payload. | N/A |
| **Guided Writing** | Fills out a section's questions and uploads files. | Sends a POST request to api/proposals/generate\_section with sanitized user input and files. | Receives and validates input. Uses an OCR library to extract text from image/PDF files. Sends the combined, pre-processed input to the AI model to generate the section draft. | Updates the JSONB column of the Proposals table with the newly generated section. |
| **Saving Progress** | Clicks "Save Draft" | Sends a POST request to api/proposals with the full JSON form data. | Receives and validates the JSON payload. Populates a Django ORM object with the request data and the user ID from the authenticated session. | Inserts a new row into the Proposals table. PostgreSQL's RLS policy implicitly checks that the user\_id matches the session's current\_user and allows the write operation. |
| **Re-engaging with Draft** | Opens a saved draft from the dashboard. | Sends a GET request to api/proposals/{id}. Renders the form by rehydrating the SurveyJS state with the JSON data. | Queries the Proposals table for the specified id. The RLS policy automatically filters the query to ensure only the authenticated user's proposals, or those shared with them, are returned. | Retrieves the row where the user\_id matches the session's current\_user, the user has an admin role, or the proposal has been explicitly shared with them. |
