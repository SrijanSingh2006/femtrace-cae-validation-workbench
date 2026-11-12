# FEMTrace | CAE Validation Workbench

A CSE portfolio project for automotive engineering quality workflows. FEMTrace ingests normalized finite-element analysis (FEA) result rows, applies explainable review criteria in a C++17 engine called by a Python API, compares design revisions, uses an unsupervised model to surface unusual result profiles, and records import and review history.

The supplied dataset is synthetic. It is for demonstrating a software workflow, not for vehicle design decisions, certification, or release.

## Why this fits the HMIE GET application

The attached campus notification calls the role Graduate Engineer Trainee (GET), lists CSE among eligible branches, and describes HMIE as an engineering-services and quality-enhancement center. It does not specify programming languages, frameworks, or a CSE-specific software stack.

HMIE's public description says its R&D support includes CAD and CAE, automobile-part design, modeling analysis, 3D CAD data, HyperMesh-based finite-element modeling, vehicle evaluation and certification support, and design improvement. FEMTrace is a CSE-built workflow tool for reviewing normalized CAE result data and tracking the review trail around it. It is aligned to that work area, but it is not an HMIE application and does not reproduce the company's internal tools.

Company-wide Hyundai Motor Group announcements also describe software-defined vehicles, connected mobility, autonomous-driving AI, and data collection, training, validation, and deployment. Those are group-wide technology directions; the sources do not say that this HMIE Hyderabad GET team uses the same stack. See docs/TECHNOLOGY_RESEARCH.md for the distinction and official sources.

## What it does

- Seeds 36 synthetic runs for six vehicle components, three revisions, and two load cases.
- Imports CSV results after validating the schema and numeric ranges.
- Calculates safety factor from yield strength divided by peak stress.
- Evaluates peak stress, displacement, safety factor, first-mode frequency, and mass target against the criteria supplied with each row.
- Classifies each run as PASS, REVIEW, or FAIL and creates a finding that contains the measured value, limit, margin, and suggested investigation.
- Shows outcome summaries by revision and numerical stress/displacement deltas between matching component/load-case revisions.
- Keeps run and finding records in SQLite; users can mark findings reviewed.
- Runs scikit-learn Isolation Forest over engineering-normalized ratios to rank unusual profiles, show robust-deviation drivers, and route them to a human reviewer.
- Keeps a CSV import ledger with a SHA-256 content fingerprint, source filename, row counts, schema version, and evaluator engine.
- Exposes a typed REST API and interactive API documentation at /docs.

## Technology stack

- C++17 command-line engine for batch evaluation of engineering criteria.
- Python 3.12, FastAPI, Pydantic, and scikit-learn for CSV validation, API routing, orchestration, and unsupervised outlier triage.
- SQLite for persistent run/finding records and traceability.
- React 18, TypeScript, Vite, and Lucide for the review interface.
- Docker Compose for the packaged deployment; its multi-stage build compiles the C++ engine.
- GitHub Actions CI compiles the native engine and builds the API dependencies and frontend bundle on each push and pull request.

HMIE's separate public experienced-software-developer listing names C/C++ and Python and mentions middleware API integration and Python tool development. That is adjacent company context, not a stated GET requirement. This project stack is a portfolio choice and not a claim about HMIE's complete internal stack.

## Run with Docker

Prerequisite: Docker Desktop with Compose enabled.

From the project directory, run:

    docker compose up --build

Then open:

    http://localhost:8000

The SQLite database is stored in the Compose volume. To stop the service, press Ctrl+C. To stop and remove the container while keeping the database volume, run:

    docker compose down

## Deploy on Render

The included `render.yaml` deploys the full Docker application as one web service. The free plan suits a portfolio demo, but it can sleep after inactivity and its filesystem is temporary. Sample records are recreated when the service starts; imported rows and finding updates may be lost after a restart or redeploy. Use a paid persistent disk or move the database to a managed database before relying on saved data. See Render's current free-service limits at https://render.com/docs/free.

To deploy, push this repository to GitHub, connect it in Render, and create a Blueprint from `render.yaml`. Render builds the Dockerfile, compiles the C++17 engine, bundles the React frontend, and serves the API and UI from one URL. The health check uses `/api/health`.

## Run locally on Windows

Open one PowerShell terminal in the project directory:

    py -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r backend\requirements.txt
    New-Item -ItemType Directory -Force backend\bin | Out-Null
    g++ -std=c++17 -O2 backend\cpp\femtrace_engine.cpp -o backend\bin\femtrace_engine.exe
    python -m uvicorn app.main:app --reload --app-dir backend

The downloadable project ZIP includes a statically linked Windows executable under backend/bin. The command above rebuilds it; compile the source for your target platform if needed. If no compatible executable is present, the API uses the equivalent Python fallback.

Open a second terminal:

    cd frontend
    npm install
    npm run dev

Visit the Vite URL printed by the frontend terminal, normally http://localhost:5173. Vite forwards API requests to the FastAPI server at port 8000. The backend API can also be explored at http://localhost:8000/docs.

To build the frontend bundle:

    cd frontend
    npm run build

## CSV data contract

The downloadable starter file is sample_data/fea_results_template.csv. The API accepts UTF-8 CSV with these columns:

    run_id, recorded_at, vehicle_program, component, design_revision, load_case, solver, mesh_elements, mass_kg, target_mass_kg, max_stress_mpa, allowable_stress_mpa, yield_strength_mpa, max_displacement_mm, allowable_displacement_mm, first_mode_hz, minimum_mode_hz, minimum_safety_factor

Each run ID is unique. Repeated IDs are skipped, and the import reports how many rows were added. Criteria travel with each row so that the review basis is visible and can be changed for demonstration purposes. For real engineering use, limits, units, solver mapping, and approval rules must be defined and reviewed by the responsible design authority.

## Review logic

- Stress and displacement move to REVIEW at 90% of the supplied upper limit and FAIL above that limit.
- Safety factor and first-mode frequency move to REVIEW near their supplied minimum and FAIL below it.
- Mass moves to REVIEW when more than 5% from target and FAIL when more than 10% from target.
- Any failed check makes the run FAIL; otherwise any review-band check makes it REVIEW; a run with all checks in range is PASS.
- Findings are rule-based and explainable. No machine-learning model or proprietary solver integration is claimed.

The AI Signals page fits an Isolation Forest to five ratios derived from stress, displacement, safety factor, modal frequency, and mass. Its displayed score is a relative percentile within the current dataset, not a probability. The top drivers are robust median absolute deviation comparisons; they are descriptive signals, not causal explanations. The model refits from the current run history when queried and has no labeled failure data.

These are illustrative software demo rules and exploratory ML signals. They are not HMIE, Hyundai, HyperMesh, or vehicle certification criteria.

## Project layout

    backend/cpp/femtrace_engine.cpp   C++17 batch evaluation engine
    backend/app/main.py          FastAPI service, SQLite schema, demo data and API logic
    frontend/src/App.tsx         Typed dashboard, search, import, comparison and finding review
    frontend/src/styles.css      Responsive interface styling
    sample_data/                 CSV import example
    docs/                        HMIE alignment, company technology research and resume guidance
    .github/workflows/ci.yml     Build checks for the C++ engine and React frontend

## AI and provenance endpoints

- `GET /api/ai/anomalies` refits Isolation Forest on stored runs and returns ranked outlier candidates with feature-level deviation indicators.
- `GET /api/imports` lists recent successful CSV imports and their fingerprints.
- `POST /api/runs/import` returns an import ID, SHA-256 fingerprint, row counts, schema version, and evaluator path in addition to the prior summary.

The seeded records and criteria remain synthetic and illustrative. The outlier model is a demonstration of unsupervised triage on a small sample, not a validated predictive maintenance or engineering safety model.

## Portfolio and interview notes

Use docs/RESUME_BULLETS.md to adapt the project entry to your actual experience. Use docs/INTERVIEW_GUIDE.md to explain the design choices without overstating company-specific integrations or engineering validity.
