# Resume entry: FEMTrace

Use only the statements that match the version you personally understand and can demonstrate.

## Project title

FEMTrace — CAE Validation and Design Review Workbench

## Suggested technologies line

C++17, Python, FastAPI, Pydantic, SQLite, React, TypeScript, Vite, REST APIs, Docker Compose

## Resume bullets

- Built a full-stack CAE result review workbench that imports finite-element result CSVs, validates the schema, and evaluates stress, displacement, safety-factor, modal-frequency, and mass-target criteria.
- Implemented a C++17 rules engine called in batch by a Python/FastAPI service, with SQLite traceability and a React/TypeScript dashboard for revision deltas, result filtering, and finding review.
- Designed explainable PASS/REVIEW/FAIL rules with explicit thresholds and recommendations, using a synthetic automotive dataset to demonstrate engineering-quality workflows.

## Compact version

Built FEMTrace, a C++17 and Python/FastAPI CAE validation workbench with a React/TypeScript dashboard to ingest simulation CSVs, compare design revisions, and track review findings in SQLite.

## Keep the claim accurate

Describe the records as synthetic, and the thresholds as example criteria. Do not write that FEMTrace is used by HMIE, is integrated with HyperMesh, validated actual vehicle parts, or achieved a measured engineering improvement. Add quantified outcomes only after you measure them on work you can reproduce. If you use the Python fallback without compiling the C++ engine, remove C++17 from the technologies line until you build and demonstrate that part.
