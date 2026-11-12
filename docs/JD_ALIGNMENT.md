# Role alignment: HMIE GET, CSE

## Requirements stated in the attached notification

- Designation: Graduate Engineer Trainee (GET).
- Degree branches listed: Mechanical, Automobile, Mechatronics, ECE, EEE, and CSE.
- Graduation year: 2027 only.
- Minimum marks: 70% or above in 10th, 12th, and graduation.
- No history of backlogs.
- Internship and work location: Hyderabad.
- Recruitment stages shown: online nomination and assessment; tool/domain test, technical interview and HR interview; three-month internship and feedback; psychometric test and pre-employment medical check; GET offer/onboarding; nine-month GET period.
- The notice also lists the internship stipend, conversion CTC, and service agreement. These are recruiting terms, not technical project requirements.

The notification does not list a CSE framework, programming language, certification, or specific software requirement. HMIE's public careers site has a separate experienced software developer listing for C/C++, Python, infotainment, middleware API integration and Python tool development; do not treat that 3-5-year listing as the GET requirement. FEMTrace demonstrates C++ and Python as an informed portfolio choice. Verify academic eligibility and current recruitment terms against the official placement communication.

## Why FEMTrace is relevant

HMIE's public company description identifies CAD/CAE work, HyperMesh-based finite-element modeling, vehicle evaluation/certification support and design improvement. FEMTrace gives a CSE applicant a concrete software artifact connected to that domain:

| HMIE work area | Project evidence |
| --- | --- |
| CAE result review | CSV importer validates a normalized simulation-result contract |
| Quality enhancement | Configurable rule checks surface values near or outside declared limits |
| Design improvement | Matching component/load-case runs show stress and displacement deltas across revisions |
| Engineering support | C++17 rules engine evaluates batches; Python/FastAPI serves runs and findings |
| Traceability | SQLite preserves run IDs, revisions, load cases, review criteria and finding status |
| Communication | React dashboard makes the review queue and evidence readable |
| Digital validation signal | scikit-learn Isolation Forest ranks unusual profiles for human triage, with feature-level deviation context |
| Data reproducibility | SHA-256 fingerprints and import metadata identify source files and how each batch was evaluated |
| Delivery practice | GitHub Actions compiles the C++ engine, checks Python sources and builds the frontend |

The project supports a discussion of data structures, API design, validation, SQL modeling, error handling, UI state, and how software can support an engineering team's review loop.

The ML feature reflects a broader digital-validation direction visible in Hyundai Motor Group communications: data-driven AI validation and anomaly detection are discussed for vehicle development. This is Group-level context, not a claim about the Hyderabad GET team or an HMIE requirement. The project implements a small, unsupervised demo and is not validated against company data.

## Limits of this alignment

- This is an independent learning project, not an HMIE assignment or company tool.
- Synthetic data is used; no HMIE or Hyundai confidential data is included.
- FEMTrace does not execute FEA or certify a component.
- It is not a HyperMesh integration. A production adapter would require approved input/export specifications and validation against the actual engineering workflow.
- The sample thresholds are illustrative and must not be used for real vehicle design decisions.
- A portfolio project cannot establish marks, graduation year, backlog history, medical eligibility, or selection outcome.
