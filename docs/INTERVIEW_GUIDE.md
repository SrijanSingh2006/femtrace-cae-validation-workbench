# Interview guide

## 45-second project explanation

“I built FEMTrace as a CSE portfolio project around automotive CAE quality workflows. It accepts a normalized CSV of simulation runs, checks the reported stress, displacement, safety factor, first-mode frequency, and mass against the limits supplied with each run, and records review findings with the source run and design revision. A C++17 engine evaluates rows in batches; a Python/FastAPI service handles validation, persistence and REST access; and a React dashboard summarizes outcomes and revision deltas. The sample data and criteria are synthetic, so the tool demonstrates a software workflow rather than making a real design or certification decision.”

## Why this project for HMIE?

“HMIE's public company profile describes CAD/CAE, HyperMesh-based finite-element modeling, vehicle evaluation/certification support, and design improvement. I chose a CSE project that supports those engineering workflows by organizing simulation results and making review criteria traceable. The public GET notice does not prescribe a CSE-specific software stack. HMIE's separate experienced software-developer listing mentions C/C++, Python, infotainment and middleware integration; I used C++ and Python in my portfolio project while keeping its domain focused on CAE.”

## Likely technical questions

### Why use rule-based evaluation rather than machine learning?

The rules need to be inspectable and traceable to stated limits. A reviewer can see the exact measurement, limit, margin and recommendation. Synthetic data is not a sound basis for claiming a predictive model.

### Why implement the evaluator in C++ and the API in Python?

The C++17 command-line engine shows a small native computation component and evaluates a batch through standard input/output. Python handles CSV validation, API routing and persistence, which keeps the data workflow readable and quick to extend. For a production tool, I would benchmark real workloads before claiming a performance advantage.

### What does the safety factor represent here?

The demo calculates yield strength divided by peak stress. That simple ratio is only meaningful when the material definition, stress measure, load case and design criterion are appropriate. The project is not a substitute for a solver or a responsible engineer's interpretation.

### Why use SQLite?

It keeps a single-user demonstration self-contained and persistent with no separate database service. For a multi-team production deployment, I would evaluate a managed relational database, identity and authorization, audit requirements, backup/retention, and concurrency needs.

### How could this connect to HyperMesh?

FEMTrace intentionally starts with a vendor-neutral normalized CSV contract and does not claim native HyperMesh integration. With approved solver output specifications, I would build and validate a separate adapter, preserve source-file/run metadata, and compare adapter output against known reference cases.

### What would you add next?

I would clarify the actual team's review process and data contract first. Candidate improvements include authenticated roles, configuration-managed criteria, signed review history, automated reports, import provenance, unit normalization, reference-case validation, and approved adapters. I would assess a production database and deployment environment with engineering stakeholders.

## Demo flow

1. Open the overview and explain that all seeded numbers are synthetic.
2. Show revision outcomes and the matched component/load-case delta table.
3. Open a failed run to show the measured value, supplied limit, and finding.
4. Import sample_data/fea_results_template.csv.
5. Explain the C++ batch evaluator, Python API, and SQLite schema.
6. State clearly that this workbench does not run HyperMesh, execute FEA, or certify a component.
