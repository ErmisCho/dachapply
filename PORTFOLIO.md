# Portfolio Profile — DACHApply

- **GitHub:** https://github.com/ErmisCho/dachapply
- **Live app:** https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io
- **Portfolio status:** Public, GitHub-pinned, and deployed
- **Last reviewed:** 2026-07-29

## Positioning

A full-stack job-intelligence platform for DACH applications that centralizes collaborative lead collection, structured job evaluation, application tracking, and evidence-based CV workflows.

## Evidence-backed highlights

- Lets trusted contacts submit job leads through invite codes while authenticated users manage jobs, evaluations, notes, follow-ups, and application status.
- Generates reusable prompts and validates imported JSON so ChatGPT-assisted enrichment and scoring remain structured without requiring a paid LLM API integration.
- Supports user-scoped JSON, CSV, and XLSX export/import with transactional server-side job imports and explicit exclusion of credentials.
- Uses Django/DRF session authentication and CSRF protection, React/TypeScript, PostgreSQL in production, and same-origin static serving through Django/WhiteNoise.
- Ships Docker and GitHub Actions deployment workflows for Azure Container Apps.

## CV-ready bullet

> Built and deployed an authenticated job-intelligence platform with Django/DRF, React/TypeScript, PostgreSQL, Docker, and Azure, combining invite-based lead intake, structured AI-assisted evaluation, application tracking, and portable user-data workflows.

## Website copy

DACHApply turns a fragmented DACH job search into one structured workflow. It combines collaborative lead intake, candidate-aware prompt generation, validated evaluation imports, prioritization, follow-ups, and portable user data in a deployed Django and React application.

## Stack

Python, Django, Django REST Framework, React, TypeScript, Tailwind CSS, PostgreSQL, WhiteNoise, Docker, GitHub Actions, Azure Container Apps, pytest.

## Evidence and boundaries

- Product flow, API, security, and deployment: `README.md`
- Backend implementation and tests: `backend/`
- Frontend implementation: `frontend/`
- Deployment automation: `.github/workflows/`
- The live application may require an account.
- Describe the AI workflow as **AI-assisted**, not autonomous: users generate prompts externally and import validated results; the project does not claim an embedded paid LLM service.
