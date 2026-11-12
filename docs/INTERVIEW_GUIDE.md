# Interview guide

## 45-second project explanation

"I built FEMTrace as a CSE portfolio project around automotive CAE quality workflows. It accepts a normalized CSV of simulation runs, checks stress, displacement, safety factor, modal frequency and mass against supplied limits, compares revisions, and records findings. A C++17 batch engine and Python/FastAPI service power a React dashboard. I also added a scikit-learn Isolation Forest for exploratory outlier triage and a SHA-256 import ledger for data lineage. The example data and criteria are synthetic, so this demonstrates a software workflow rather than a real design or certification decision."

## Why this project for HMIE?

“HMIE's public company profile describes CAD/CAE, HyperMesh-based finite-element modeling, vehicle evaluation/certification support, and design improvement. I chose a CSE project that supports those engineering workflows by organizing simulation results and making review criteria traceable. The public GET notice does not prescribe a CSE-specific software stack. HMIE's separate experienced software-developer listing mentions C/C++, Python, infotainment and middleware integration; I used C++ and Python in my portfolio project while keeping its domain focused on CAE.”

## Likely technical questions

### Why keep rules if the project now includes machine learning?

Rules remain the authoritative check because they map a measured value to an explicit limit and produce an inspectable finding. Isolation Forest is a separate, unsupervised triage signal: it ranks unusual combinations of normalized metrics without failure labels. The sample is small and synthetic, so the signal is not a calibrated probability, a causal explanation, a failure prediction, or a safety decision. A human reviewer must inspect it.

### How does the anomaly ranking work?

The API refits a deterministic scikit-learn Isolation Forest on stress and displacement utilization, safety-factor and modal-frequency shortfall ratios, and mass deviation. It reports each run's relative anomaly percentile within the current dataset. For context, it ranks the input metrics by robust median absolute deviation from their dataset medians. These are model-level ranking and descriptive driver indicators, not SHAP values or causal attributions.

### Why implement the evaluator in C++ and the API in Python?

The C++17 command-line engine shows a small native computation component and evaluates a batch through standard input/output. Python handles CSV validation, API routing and persistence, which keeps the data workflow readable and quick to extend. For a production tool, I would benchmark real workloads before claiming a performance advantage.

### What does the safety factor represent here?

The demo calculates yield strength divided by peak stress. That simple ratio is only meaningful when the material definition, stress measure, load case and design criterion are appropriate. The project is not a substitute for a solver or a responsible engineer's interpretation.

### Why use SQLite?

It keeps a single-user demonstration self-contained and persistent with no separate database service. For a multi-team production deployment, I would evaluate a managed relational database, identity and authorization, audit requirements, backup/retention, and concurrency needs.

### How could this connect to HyperMesh?

FEMTrace intentionally starts with a vendor-neutral normalized CSV contract and does not claim native HyperMesh integration. With approved solver output specifications, I would build and validate a separate adapter, preserve source-file/run metadata, and compare adapter output against known reference cases.

### What would you add next?

I would validate the data contract and model behavior against approved, representative historical data before considering operational use. Then I would add versioned criteria, authenticated reviewer roles, unit normalization, reference-case validation, and a vetted solver adapter. I would also plan a production database and deployment environment with engineering stakeholders.

## Demo flow

1. Open the overview and explain that all seeded numbers are synthetic.
2. Show revision outcomes and the matched component/load-case delta table.
3. Open a failed run to show the measured value, supplied limit, and finding.
4. Import sample_data/fea_results_template.csv.
5. Open AI Signals and explain why the score is relative and exploratory; point out the input driver details.
6. Show the import ledger and explain its SHA-256 fingerprint, row counts and evaluator version.
7. Explain the C++ batch evaluator, Python API, SQLite schema and GitHub Actions build workflow.
8. State clearly that this workbench does not run HyperMesh, execute FEA, or certify a component.
