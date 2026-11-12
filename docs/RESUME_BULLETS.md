# Resume entry: FEMTrace

Use only the statements that match the version you personally understand and can demonstrate.

## Project title

FEMTrace — CAE Validation and Design Review Workbench

## Suggested technologies line

C++17, Python, FastAPI, Pydantic, scikit-learn (Isolation Forest), SQLite, React, TypeScript, Vite, REST APIs, Docker, GitHub Actions

## Resume bullets

- Built a full-stack CAE result review workbench that imports finite-element result CSVs, validates the schema, and evaluates stress, displacement, safety-factor, modal-frequency, and mass-target criteria.
- Implemented a C++17 rules engine called in batch by a Python/FastAPI service, with SQLite traceability and a React/TypeScript dashboard for revision deltas, result filtering, and finding review.
- Added an unsupervised scikit-learn Isolation Forest to rank unusual engineering-result profiles and surface robust-deviation drivers for human review; clearly separated exploratory outlier triage from rule-based checks.
- Recorded CSV import provenance with SHA-256 fingerprints, schema and engine versions, and duplicate counts; added GitHub Actions build checks for the API, C++17 engine and frontend.
- Designed explainable PASS/REVIEW/FAIL rules with explicit thresholds and recommendations, using synthetic automotive data to demonstrate engineering-quality workflows.

## Compact version

Built FEMTrace, a C++17 and Python/FastAPI CAE validation workbench with a React/TypeScript dashboard, scikit-learn outlier triage, and SHA-256 import lineage for simulation result review.

## Keep the claim accurate

Describe the records as synthetic, and the thresholds as example criteria. Do not write that FEMTrace is used by HMIE, is integrated with HyperMesh, validated actual vehicle parts, or achieved a measured engineering improvement. Add quantified outcomes only after you measure them on work you can reproduce. If you use the Python fallback without compiling the C++ engine, remove C++17 from the technologies line until you build and demonstrate that part.

When discussing the ML component, call it exploratory, unsupervised outlier triage on a small synthetic dataset. Do not call its relative score a probability or claim failure prediction, causal explanations, or safety validation.
