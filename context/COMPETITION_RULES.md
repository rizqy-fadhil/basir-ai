# COMPETITION_RULES.md

## Purpose

This document defines the competition constraints that every human contributor and AI agent must follow while developing the AIC COMPFEST 18 project.

The goal is to prevent actions that could invalidate the submission, violate competition rules, misrepresent the product, or create inconsistencies between the repository, proposal, and demonstration videos.

When a requested task conflicts with this document, the AI agent must stop, explain the conflict, and request human confirmation before continuing.

---

## 1. Core Competition Scope

- The project must be an original AI-based innovation aligned with the theme **AI for the Backbone of the Economy**.
- The solution should address a relevant problem in one or more of these areas:
  - Smart Manufacturing
  - Smart Logistics
  - Smart Commerce
- AI must have a meaningful role in solving the problem. Do not add AI only as a decorative or forced feature.
- The same project developed during the preliminary stage must be continued if the team advances to the final stage.

---

## 2. Originality and Development Integrity

The AI agent must ensure that:

- The project is not a continuation of a product or repository developed before the official competition period.
- Existing external projects are not copied, rebranded, or submitted as original work.
- External libraries, frameworks, public datasets, public APIs, and pre-trained models may be used only as supporting components.
- Any pre-trained model or AI API used must be adapted, configured, fine-tuned, or integrated specifically for the project's use case.
- All important technical decisions must be explainable and traceable.
- Generated code must not conceal its source, purpose, or behavior.
- No fabricated experiment, metric, dataset, feature, model result, user feedback, or deployment claim may be added to the repository or proposal.

If the origin or eligibility of an asset is unclear, do not use it until a human verifies that it is allowed.

---

## 3. MVP Development Boundaries

The preliminary submission should focus on a functional **Minimum Viable Product**, not a production-scale system.

### Frontend

The frontend only needs to support the primary user flow:

1. Receive the main user input.
2. Process the input.
3. Display the AI-generated result.

Do not prioritize unnecessary features such as:

- advanced analytics dashboards;
- complex authentication systems;
- detailed usage history;
- unrelated administrative modules;
- features that do not support the core use case.

### Backend

The backend may focus on synchronous processing required by the main use case.

Avoid unnecessary complexity such as:

- distributed infrastructure;
- complex asynchronous pipelines;
- background jobs that are not essential;
- production-scale observability;
- automatic data collection unrelated to the demonstration;
- unnecessary external service dependencies.

### AI Model

The AI component must at minimum:

- accept the required input;
- run the intended inference or processing flow;
- return a meaningful output;
- be reproducible during local demonstration.

The preliminary MVP does not require:

- automatic retraining;
- automatic hyperparameter tuning;
- large-scale batch testing;
- automated feedback loops;
- production deployment infrastructure.

Do not overbuild features that reduce stability or make local evaluation harder.

---

## 4. Repository Requirements

The submitted repository must remain suitable for public review and local evaluation.

The AI agent must maintain:

- a public GitHub-compatible repository;
- complete source code required to run the MVP;
- a clear `README.md`;
- clear setup and usage instructions;
- a working `docker-compose.yml` or equivalent Docker Compose configuration;
- reproducible local execution;
- a clean and understandable project structure;
- descriptive commit history.

### Commit Rules

Use Conventional Commits where appropriate, for example:

- `feat: add demand forecasting endpoint`
- `fix: handle missing warehouse input`
- `refactor: separate inference service from API layer`
- `docs: update local setup instructions`
- `test: add inference validation cases`

Do not:

- create misleading commit messages;
- squash all development into one unexplained final commit;
- rewrite history in a way that hides the development process;
- commit secrets, credentials, private keys, tokens, or private datasets;
- commit generated artifacts that are not required for evaluation;
- modify the repository after the official competition cutoff.

---

## 5. Local Reproducibility

The project must be runnable by the judges in a local environment.

The AI agent must prioritize:

- deterministic and documented setup steps;
- pinned or clearly defined dependencies;
- environment-variable templates such as `.env.example`;
- safe handling of credentials;
- meaningful error messages;
- mock or sample inputs where needed;
- instructions for running the application through Docker Compose;
- instructions for testing the main user flow.

Do not assume that judges have access to:

- the developer's local files;
- private cloud resources;
- private databases;
- hidden credentials;
- proprietary hardware;
- undocumented manual setup steps.

For hardware-integrated products, provide a **mock data mode** so that the software can still be evaluated without the physical hardware.

---

## 6. Dataset and Model Usage

Allowed data sources include:

- public datasets;
- properly licensed datasets;
- synthetic data created for the project.

The AI agent must:

- document the origin of every dataset;
- document preprocessing steps;
- explain important assumptions and limitations;
- avoid using private, leaked, unauthorized, or personally sensitive data;
- avoid presenting synthetic data as real-world collected data;
- preserve attribution and license notices when required.

For models and APIs:

- document the model or API used;
- explain why it was selected;
- explain how it is adapted to the project;
- document important parameters;
- describe the inference flow;
- avoid claiming model ownership when using an external model.

---

## 7. Identity and Blind-Review Safety

Do not display or embed the team's educational institution identity in competition materials where it is prohibited.

The AI agent must check for institution identity in:

- application screens;
- source code comments;
- repository badges;
- README content;
- screenshots;
- demo videos;
- proposal pages;
- metadata;
- filenames;
- sample data;
- logos and watermarks.

When uncertain, use neutral team and project identifiers.

---

## 8. Required Submission Components

The preliminary submission consists of these main components:

1. Public source-code repository.
2. Video Proof of Work.
3. Promotional video.
4. PDF proposal.

All components must describe the same product, features, technical flow, and level of completion.

The AI agent must prevent contradictions between:

- repository implementation;
- README instructions;
- proposal claims;
- Proof of Work video;
- promotional video.

---

## 9. Proof of Work Rules

The Proof of Work video must truthfully show the actual condition of the MVP at submission time.

It should demonstrate:

- the application being run;
- the main user flow;
- implemented features;
- terminal or execution process where relevant;
- the actual output produced by the system;
- timestamps or visible indicators that support authenticity;
- known bugs, limitations, or unfinished parts when applicable.

The AI agent must not help create a misleading demonstration.

Do not:

- simulate a working feature that does not exist;
- replace real output with edited output;
- hide failures through deceptive cuts;
- present mock results as real model inference without disclosure;
- claim that a feature is complete when it is not implemented;
- show a feature in the promotional video that cannot be shown in the Proof of Work video.

Fast-forwarding waiting periods is acceptable, but the core execution flow must remain understandable and honest.

---

## 10. Promotional Video Rules

The promotional video should explain:

- the problem being addressed;
- the target user or stakeholder;
- how the proposed solution works;
- how AI contributes to the solution;
- the expected benefit or impact;
- the product-development story.

The video may use storytelling, screen recordings, or camera footage, but all statements must remain consistent with the actual MVP.

Do not exaggerate:

- deployment status;
- active users;
- partnerships;
- measured impact;
- model accuracy;
- commercial adoption;
- hardware readiness;
- regulatory approval.

---

## 11. Proposal Requirements

The proposal must explain both the product and the development process.

It should include at least:

- project title and team identifier;
- background and problem statement;
- project objectives;
- expected benefits;
- dataset acquisition or generation process;
- data preprocessing;
- model-development process for each AI feature;
- model integration into the application;
- system architecture;
- technical decision rationale;
- supporting analysis or experiments;
- limitations;
- conclusion.

The proposal must not be only a feature list. It should show why technical and product decisions were made.

The AI agent must not insert:

- fake citations;
- fake experiments;
- fake references;
- fabricated metrics;
- unsupported market claims;
- copied text without attribution;
- claims that cannot be verified from the repository or available evidence.

Keep the proposal within the official page limit. Cover, bibliography, and appendices may follow the exclusions stated in the official rulebook.

---

## 12. Evaluation Priorities

When choosing between implementation options, prioritize the areas used in preliminary judging:

1. **Technology implementation and architecture maturity**
   - correct technology selection;
   - reliable AI inference;
   - clear separation of components;
   - understandable architecture;
   - sufficient documentation.

2. **Originality and social or business impact**
   - relevant problem;
   - meaningful differentiation;
   - clear target users;
   - credible expected impact.

3. **MVP readiness for the final stage**
   - working core flow;
   - stable local execution;
   - clear limitations;
   - architecture that can be extended.

4. **Proposal and development quality**
   - coherent methodology;
   - traceable decisions;
   - reflective and iterative process;
   - clear technical reasoning.

5. **Theme relevance**
   - strong connection to the economic backbone theme;
   - AI use that is necessary and appropriate.

6. **Business value and governance**
   - realistic adoption plan;
   - business model or value proposition;
   - ethical considerations;
   - responsible AI;
   - regulatory awareness.

Do not sacrifice a stable and honest MVP merely to add more features.

---

## 13. Prohibited Actions

The AI agent must not perform or assist with any of the following:

- copying another team's project;
- reusing an ineligible pre-competition project;
- fabricating data, metrics, users, or results;
- hiding known failures from the judges;
- creating deceptive demo footage;
- altering Git history to misrepresent development;
- bypassing the official submission process;
- modifying the project after the official cutoff;
- exposing secrets or private information;
- using unauthorized datasets or code;
- including prohibited institution identity;
- introducing malware, tracking code, or unrelated telemetry;
- generating unsupported claims in the proposal or promotional materials;
- making the project dependent on undocumented private infrastructure.

---

## 14. AI Agent Operating Policy

Before making a change, the AI agent should verify that the change:

1. supports the core competition use case;
2. is allowed under the originality rules;
3. can be documented honestly;
4. can be reproduced locally;
5. does not expose secrets or restricted data;
6. does not contradict the proposal or demonstration materials;
7. does not introduce unnecessary complexity;
8. can be completed before the official cutoff.

The AI agent must request human approval before:

- changing the core project scope;
- replacing the primary AI model;
- changing the dataset source;
- adding a paid or private external dependency;
- removing a previously demonstrated feature;
- rewriting Git history;
- changing claims already used in the proposal or videos;
- using any asset with unclear ownership or licensing.

---

## 15. Final Compliance Checklist

Before submission, verify all of the following:

- [ ] The project is original and eligible.
- [ ] The solution is relevant to the official theme.
- [ ] AI has a meaningful and explainable role.
- [ ] The core user flow works.
- [ ] The application can run locally.
- [ ] Docker Compose configuration works.
- [ ] The repository is public and accessible.
- [ ] The README contains complete setup and usage instructions.
- [ ] No credentials or private data are committed.
- [ ] Dataset and model sources are documented.
- [ ] Commit history is descriptive and legitimate.
- [ ] No repository changes are made after the official cutoff.
- [ ] Institution identity is not exposed where prohibited.
- [ ] The Proof of Work shows the real MVP condition.
- [ ] The promotional video does not exaggerate product readiness.
- [ ] Every demonstrated feature exists in the repository.
- [ ] Proposal claims are supported by evidence.
- [ ] Repository, proposal, and videos are mutually consistent.
- [ ] All submission links are accessible.
- [ ] The final submitted version is the intended version.

---

## Source of Truth

This document is an operational summary for project contributors and AI agents. If any statement here conflicts with the official AIC COMPFEST 18 rulebook or an official announcement from the organizers, the official rulebook and organizer clarification take precedence.
