# Job Application Adaptation Rules

## 1. Global honesty rules

- Do not invent experience, tools, responsibilities, production ownership, or metrics.
- Prefer honest adjacent wording over keyword stuffing.
- If a job asks for a tool I do not clearly have, do not add it as experience.
- It is acceptable to show adjacent experience and learning ability.
- Do not claim production ownership of Kubernetes, Terraform, Helm, GitOps, MLflow, Databricks, Snowflake, Spark, Airflow, GCP, Azure OpenAI production, full MLOps, full CI/CD, model monitoring, or observability unless explicitly evidenced.
- Elasticsearch/OpenSearch must always be phrased as:
  “worked with an existing Elasticsearch/OpenSearch-based retrieval stack”
  German:
  “Arbeit mit einem bestehenden Elasticsearch/OpenSearch-basierten Retrieval-Stack”
- German level:
  English CV:
  “German: Professional working proficiency, Goethe-Zertifikat B2, C1 course in progress”
  German CV:
  “Deutsch: Beruflich sicher, Goethe-Zertifikat B2, C1-Kurs in Arbeit”
- Portfolio link should be included where useful:
  https://ermischo.github.io

## 2. CV adaptation rules

### General CV rules

- Maximum 2 pages.
- Do not remove important bullets too early. First fix spacing and layout.
- Do not shrink the CV into unreadable text.
- Avoid orphaned headings: an employer heading must not appear at the bottom of a page while its bullets start on the next page.
- Keep each job heading with at least the first 2 bullets.
- Use `needspace` in LaTeX if needed to prevent bad page breaks.
- Use the available 2 pages properly. Do not underuse space if important experience can be shown.
- Use target-specific filenames.
- Do not edit protected base files.

### Experience rules

- RISE should usually show AI/Search, RAG, ingestion, indexing, retrieval, FastAPI, existing Elasticsearch/OpenSearch stack, and telemetry/data-flow risk reduction.
- RISE date is:
  “Mai 2025 -- Sep 2025”
- Kapsch should usually have at least 3 bullets.
- Huawei should usually have 4 bullets when space allows.
- Huawei title can be:
  “Softwareingenieur / Team Lead”
- Huawei should show leadership naturally:
  “Leitung eines kleinen Engineering-Teams mit Verantwortung für Priorisierung, Aufgabenkoordination, Review technischer Implementierungen und Abstimmung mit Stakeholdern.”
- Do not write:
  “officially acted as Team Lead”
- Citibank should usually have 4 bullets when relevant, especially for security, platform, regulated, ML/security, or enterprise roles.
- Citibank should show Python/Java, CVE/security-data workflows, SQL, Linux hardening, regulated enterprise environment.

### Project rules

Prioritize projects depending on job type:

For ML Engineer:
1. SMS Spam Detection NLP Platform
2. Asynchrone RAG-Pipeline
3. Event Analytics Pipeline
4. Agentisches RAG-System if space allows

For AI/RAG Engineer:
1. Asynchrone RAG-Pipeline
2. Agentisches RAG-System
3. DACHApply or SMS NLP depending on job
4. Event Analytics Pipeline if data angle matters

For Backend Engineer:
1. DACHApply
2. Asynchrone RAG-Pipeline
3. Event Analytics Pipeline
4. Backend Webshop only if space and relevant

For Security/platform-adjacent roles:
1. Citibank security-data workflows
2. RISE telemetry/data-flow risk reduction
3. Asynchrone RAG-Pipeline
4. DACHApply or Event Analytics depending on role

## 3. Motivation letter adaptation rules

### General motivation-letter rules

- Motivation letter must fit on 1 page.
- Do not repeat the CV in prose.
- Keep it specific to the role.
- Use 4–5 compact paragraphs.
- Keep tone professional, direct, and natural.
- Avoid exaggerated enthusiasm.
- Avoid generic phrases like “I am highly passionate” unless clearly grounded.
- Use concrete evidence from 2–3 strongest experiences/projects only.
- End with a concise, confident closing.

### Recommended structure

1. Opening:
   Why this role is relevant and what intersection it represents.

2. Core fit:
   1 paragraph on strongest professional experience for the job.

3. Project evidence:
   1 paragraph on the most relevant portfolio project or projects.

4. Additional credibility:
   1 paragraph on earlier enterprise/security/backend/leadership experience.

5. Closing:
   How I would contribute to the team and request for interview.

### Motivation-letter style

- German letters should use formal “Sie/Ihr” unless the company contact writes informally.
- Prefer:
  “möchte ich meine Erfahrung einbringen”
  over:
  “bin ich überzeugt, der perfekte Kandidat zu sein”
- Keep paragraphs short enough for one page.
- If the letter is too long, remove detail before shrinking font.

## 4. Role-type positioning

### Machine Learning Engineer

Position as:
Python-focused Machine Learning Engineer / Software Engineer with practical ML engineering, reproducible evaluation, FastAPI serving, data quality, RAG, Generative AI, Docker/Azure project deployment, and security-aware engineering.

Emphasize:
- scikit-learn
- NLP
- TF-IDF
- logistic regression
- F1, Precision/Recall
- grouped evaluation
- duplicate-safe train/test split
- FastAPI serving
- Docker
- Azure Container Apps project deployment
- RAG
- data pipelines
- Pandas, NumPy, SQL, Parquet, DuckDB

Do not overclaim:
- PyTorch
- deep learning production
- ML research
- full MLOps ownership
- model monitoring ownership

### AI Engineer / RAG Engineer

Position as:
Backend-focused AI Engineer building reliable RAG, search, ingestion, retrieval, async processing, APIs, and guardrailed AI workflows.

Emphasize:
- FastAPI
- RAG
- LangChain
- LangGraph
- RabbitMQ
- Redis
- retrieval guardrails
- job tracking
- retry handling
- document ingestion
- existing Elasticsearch/OpenSearch stack

### Python Backend Engineer

Position as:
Python backend engineer with FastAPI, Django, REST APIs, SQL, async workflows, Docker, testing, automation, and reliability-focused development.

Emphasize:
- APIs
- SQL/PostgreSQL
- FastAPI/Django
- background jobs
- validation
- testing
- Docker/Linux
- practical AI integration only when relevant

### Platform / Security-adjacent Engineer

Position as:
Security-aware backend/platform-adjacent engineer with Python/Java, Linux, Docker/Kubernetes-adjacent exposure, security-data workflows, CVE automation, telemetry/data-flow risk reduction, and regulated enterprise experience.

Do not overclaim:
- cloud security ownership
- IAM ownership
- Terraform/Helm
- full Kubernetes administration
- incident response ownership
- healthcare compliance ownership

### Elastic/Search roles

Position as:
Backend/Search-adjacent engineer with RAG/search experience, existing Elasticsearch/OpenSearch retrieval stack exposure, Python APIs, Linux, automation, and reliability focus.

Do not overclaim:
- Elasticsearch administrator ownership
- ECK ownership
- Elastic Cloud administration
- Fleet/Logstash/Grok ownership
- shard/heap/GC production tuning ownership

## 5. Layout rules

### CV layout

- Maximum 2 pages.
- Use full 2 pages if needed.
- Avoid orphaned headings.
- Prefer shortening projects before removing key experience bullets.
- Do not reduce Huawei below 4 bullets when leadership is relevant.
- Do not reduce Citibank below 4 bullets when security/platform/enterprise relevance matters.
- If space is tight:
  1. remove least relevant project
  2. shorten project bullets
  3. slightly adjust spacing
  4. only then reduce experience bullets

### Motivation-letter layout

- Must be 1 page.
- Use margins around 2.0–2.2 cm if needed.
- Use `\setstretch{1.0}` or similar.
- Do not make it visually cramped.
- Remove repetition before reducing readability.

## 6. Final checks for every application

Before final export, verify:

- CV max 2 pages.
- Motivation letter max 1 page.
- No text overlap.
- No orphaned employer headings.
- Photo loads correctly if used.
- Links work.
- No leftover prompt/comment text after `\end{document}`.
- No invented tools.
- No exaggerated production ownership.
- Correct target filename.
- Correct company and role name.
- German formality level is appropriate.
- Portfolio link is included where useful.
