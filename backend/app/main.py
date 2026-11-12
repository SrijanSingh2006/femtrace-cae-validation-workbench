from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import sqlite3
import subprocess
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sklearn.ensemble import IsolationForest
import sklearn


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("FEMTRACE_DATA_DIR", str(PROJECT_ROOT / "data")))
DB_PATH = DATA_DIR / "femtrace.sqlite3"
ENGINE_SUFFIX = ".exe" if os.name == "nt" else ""
ENGINE_PATH = Path(os.getenv("FEMTRACE_ENGINE_PATH", str(PROJECT_ROOT / "backend" / "bin" / ("femtrace_engine" + ENGINE_SUFFIX))))
STATIC_DIR = Path(os.getenv("FEMTRACE_STATIC_DIR", str(PROJECT_ROOT / "static")))
REQUIRED_COLUMNS = {
    "run_id", "recorded_at", "vehicle_program", "component", "design_revision",
    "load_case", "solver", "mesh_elements", "mass_kg", "target_mass_kg",
    "max_stress_mpa", "allowable_stress_mpa", "yield_strength_mpa",
    "max_displacement_mm", "allowable_displacement_mm", "first_mode_hz",
    "minimum_mode_hz", "minimum_safety_factor",
}


class SimulationRun(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    run_id: str = Field(min_length=1, max_length=80)
    recorded_at: datetime
    vehicle_program: str = Field(min_length=1, max_length=100)
    component: str = Field(min_length=1, max_length=100)
    design_revision: str = Field(min_length=1, max_length=40)
    load_case: str = Field(min_length=1, max_length=100)
    solver: str = Field(min_length=1, max_length=80)
    mesh_elements: int = Field(ge=1, le=100_000_000)
    mass_kg: float = Field(gt=0, le=100_000)
    target_mass_kg: float = Field(gt=0, le=100_000)
    max_stress_mpa: float = Field(gt=0, le=100_000)
    allowable_stress_mpa: float = Field(gt=0, le=100_000)
    yield_strength_mpa: float = Field(gt=0, le=100_000)
    max_displacement_mm: float = Field(ge=0, le=100_000)
    allowable_displacement_mm: float = Field(gt=0, le=100_000)
    first_mode_hz: float = Field(gt=0, le=100_000)
    minimum_mode_hz: float = Field(gt=0, le=100_000)
    minimum_safety_factor: float = Field(gt=0, le=100)


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS simulation_runs (
                run_id TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL,
                vehicle_program TEXT NOT NULL,
                component TEXT NOT NULL,
                design_revision TEXT NOT NULL,
                load_case TEXT NOT NULL,
                solver TEXT NOT NULL,
                mesh_elements INTEGER NOT NULL,
                mass_kg REAL NOT NULL,
                target_mass_kg REAL NOT NULL,
                max_stress_mpa REAL NOT NULL,
                allowable_stress_mpa REAL NOT NULL,
                yield_strength_mpa REAL NOT NULL,
                max_displacement_mm REAL NOT NULL,
                allowable_displacement_mm REAL NOT NULL,
                first_mode_hz REAL NOT NULL,
                minimum_mode_hz REAL NOT NULL,
                minimum_safety_factor REAL NOT NULL,
                safety_factor REAL NOT NULL,
                stress_margin_pct REAL NOT NULL,
                displacement_margin_pct REAL NOT NULL,
                status TEXT NOT NULL,
                finding_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES simulation_runs(run_id) ON DELETE CASCADE,
                component TEXT NOT NULL,
                design_revision TEXT NOT NULL,
                load_case TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                measured_value REAL NOT NULL,
                limit_value REAL NOT NULL,
                unit TEXT NOT NULL,
                gap_pct REAL NOT NULL,
                recommendation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                UNIQUE(run_id, rule_name)
            );
            CREATE TABLE IF NOT EXISTS import_batches (
                import_id TEXT PRIMARY KEY,
                source_filename TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                received_rows INTEGER NOT NULL,
                inserted_rows INTEGER NOT NULL,
                duplicate_rows INTEGER NOT NULL,
                schema_version TEXT NOT NULL,
                evaluator_engine TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_runs_component_date
                ON simulation_runs(component, recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_status
                ON simulation_runs(status);
            CREATE INDEX IF NOT EXISTS idx_findings_status
                ON findings(status, severity);
            """
        )


RULES = [
    ("Maximum stress", "max_stress_mpa", "allowable_stress_mpa", "MPa",
     "Review material assumptions, load application, local stress concentration and mesh convergence."),
    ("Peak displacement", "max_displacement_mm", "allowable_displacement_mm", "mm",
     "Review stiffness, boundary conditions and load path; confirm the displacement limit with the design owner."),
    ("Safety factor", "safety_factor", "minimum_safety_factor", "x",
     "Review material properties and the governing load case; confirm the required margin with the design owner."),
    ("First mode frequency", "first_mode_hz", "minimum_mode_hz", "Hz",
     "Review stiffness and mass distribution, then compare the mode shape with the intended operating range."),
    ("Mass target", "mass_kg", "target_mass_kg", "kg",
     "Review the latest geometry and mass-property extraction against the program target."),
]


def evaluate(run: SimulationRun) -> tuple[str, float, float, float, list[dict[str, Any]]]:
    values = run.model_dump()
    safety_factor = run.yield_strength_mpa / run.max_stress_mpa
    values["safety_factor"] = safety_factor

    checks = [
        ("Maximum stress", run.max_stress_mpa, run.allowable_stress_mpa, "MPa", "upper"),
        ("Peak displacement", run.max_displacement_mm, run.allowable_displacement_mm, "mm", "upper"),
        ("Safety factor", safety_factor, run.minimum_safety_factor, "x", "lower"),
        ("First mode frequency", run.first_mode_hz, run.minimum_mode_hz, "Hz", "lower"),
        ("Mass target", run.mass_kg, run.target_mass_kg, "kg", "mass"),
    ]
    findings: list[dict[str, Any]] = []
    rank = {"PASS": 0, "REVIEW": 1, "FAIL": 2}

    for rule_name, measured, limit, unit, direction in checks:
        if direction == "upper":
            gap_pct = ((measured - limit) / limit) * 100
            status = "FAIL" if measured > limit else ("REVIEW" if measured >= limit * 0.9 else "PASS")
        elif direction == "lower":
            gap_pct = ((limit - measured) / limit) * 100
            status = "FAIL" if measured < limit else ("REVIEW" if measured < limit * 1.1 else "PASS")
        else:
            gap_pct = ((measured - limit) / limit) * 100
            absolute_gap = abs(gap_pct)
            status = "FAIL" if absolute_gap > 10 else ("REVIEW" if absolute_gap > 5 else "PASS")

        if status != "PASS":
            rule = next(item for item in RULES if item[0] == rule_name)
            findings.append({
                "rule_name": rule_name,
                "severity": "Critical" if status == "FAIL" else "Monitor",
                "measured_value": round(measured, 4),
                "limit_value": round(limit, 4),
                "unit": unit,
                "gap_pct": round(gap_pct, 2),
                "recommendation": rule[4],
                "status": status,
            })

    overall = max((item["status"] for item in findings), key=lambda status: rank[status], default="PASS")
    stress_margin = ((run.allowable_stress_mpa - run.max_stress_mpa) / run.allowable_stress_mpa) * 100
    displacement_margin = (
        (run.allowable_displacement_mm - run.max_displacement_mm)
        / run.allowable_displacement_mm
    ) * 100
    return overall, safety_factor, stress_margin, displacement_margin, findings


def evaluate_batch(runs: list[SimulationRun]) -> list[tuple[str, float, float, float, list[dict[str, Any]]]]:
    if not ENGINE_PATH.is_file():
        return [evaluate(run) for run in runs]
    lines = []
    for run in runs:
        values = [
            run.max_stress_mpa, run.allowable_stress_mpa, run.yield_strength_mpa,
            run.max_displacement_mm, run.allowable_displacement_mm, run.first_mode_hz,
            run.minimum_mode_hz, run.minimum_safety_factor, run.mass_kg, run.target_mass_kg,
        ]
        lines.append(" ".join(str(value) for value in values))
    result = subprocess.run(
        [str(ENGINE_PATH)], input="\n".join(lines) + "\n", text=True,
        encoding="utf-8", capture_output=True, timeout=60, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("C++ evaluation engine failed: " + result.stderr[:500])
    output_rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    if len(output_rows) != len(runs):
        raise RuntimeError("C++ evaluation engine returned an unexpected row count")
    evaluations = []
    for item in output_rows:
        findings = [{
            **finding,
            "measured_value": round(finding["measured_value"], 4),
            "limit_value": round(finding["limit_value"], 4),
            "gap_pct": round(finding["gap_pct"], 2),
        } for finding in item["findings"]]
        evaluations.append((
            item["status"], round(item["safety_factor"], 4),
            round(item["stress_margin_pct"], 2),
            round(item["displacement_margin_pct"], 2), findings,
        ))
    return evaluations


def save_run(
    db: sqlite3.Connection,
    run: SimulationRun,
    evaluation: tuple[str, float, float, float, list[dict[str, Any]]] | None = None,
) -> bool:
    recorded_at = run.recorded_at
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    run_data = run.model_dump()
    run_data["recorded_at"] = recorded_at.astimezone(timezone.utc).isoformat()
    status, safety_factor, stress_margin, displacement_margin, findings = evaluation or evaluate(run)

    cursor = db.execute(
        """
        INSERT OR IGNORE INTO simulation_runs (
            run_id, recorded_at, vehicle_program, component, design_revision, load_case,
            solver, mesh_elements, mass_kg, target_mass_kg, max_stress_mpa,
            allowable_stress_mpa, yield_strength_mpa, max_displacement_mm,
            allowable_displacement_mm, first_mode_hz, minimum_mode_hz,
            minimum_safety_factor, safety_factor, stress_margin_pct,
            displacement_margin_pct, status, finding_count
        ) VALUES (
            :run_id, :recorded_at, :vehicle_program, :component, :design_revision, :load_case,
            :solver, :mesh_elements, :mass_kg, :target_mass_kg, :max_stress_mpa,
            :allowable_stress_mpa, :yield_strength_mpa, :max_displacement_mm,
            :allowable_displacement_mm, :first_mode_hz, :minimum_mode_hz,
            :minimum_safety_factor, :safety_factor, :stress_margin_pct,
            :displacement_margin_pct, :status, :finding_count
        )
        """,
        {
            **run_data,
            "safety_factor": round(safety_factor, 4),
            "stress_margin_pct": round(stress_margin, 2),
            "displacement_margin_pct": round(displacement_margin, 2),
            "status": status,
            "finding_count": len(findings),
        },
    )
    if cursor.rowcount == 0:
        return False

    for finding in findings:
        db.execute(
            """
            INSERT INTO findings (
                finding_id, run_id, component, design_revision, load_case, rule_name,
                severity, measured_value, limit_value, unit, gap_pct, recommendation, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
            """,
            (
                str(uuid.uuid4()), run.run_id, run.component, run.design_revision,
                run.load_case, finding["rule_name"], finding["severity"],
                finding["measured_value"], finding["limit_value"], finding["unit"],
                finding["gap_pct"], finding["recommendation"],
            ),
        )
    return True


def make_demo_runs() -> list[SimulationRun]:
    now = datetime.now(timezone.utc)
    components = [
        {"name": "Front subframe", "program": "Crossover EV", "stress": 238, "allow": 285,
         "yield": 355, "disp": 2.0, "disp_limit": 3.0, "mass": 16.2, "freq": 34, "freq_min": 28},
        {"name": "Battery enclosure", "program": "Crossover EV", "stress": 142, "allow": 185,
         "yield": 250, "disp": 1.1, "disp_limit": 2.0, "mass": 34.7, "freq": 42, "freq_min": 32},
        {"name": "Steering knuckle", "program": "Compact EV", "stress": 248, "allow": 305,
         "yield": 420, "disp": 0.72, "disp_limit": 1.1, "mass": 5.4, "freq": 66, "freq_min": 48},
        {"name": "Seat rail", "program": "Compact EV", "stress": 188, "allow": 250,
         "yield": 350, "disp": 1.6, "disp_limit": 2.7, "mass": 4.1, "freq": 51, "freq_min": 38},
        {"name": "Control arm", "program": "SUV platform", "stress": 214, "allow": 275,
         "yield": 355, "disp": 1.4, "disp_limit": 2.3, "mass": 7.8, "freq": 47, "freq_min": 35},
        {"name": "Rear crossmember", "program": "SUV platform", "stress": 205, "allow": 268,
         "yield": 355, "disp": 2.2, "disp_limit": 3.2, "mass": 13.1, "freq": 31, "freq_min": 26},
    ]
    revisions = [("Rev A", 0.93), ("Rev B", 0.97), ("Rev C", 1.0)]
    runs: list[SimulationRun] = []
    for part_index, part in enumerate(components):
        for revision_index, (revision, factor) in enumerate(revisions):
            for load_index, load_case in enumerate(("Vertical load", "Cornering load")):
                scale = factor * (1.0 + (0.035 if load_index else 0.0))
                stress = part["stress"] * scale
                displacement = part["disp"] * factor * (1.0 + (0.08 if load_index else 0.0))
                mass = part["mass"] * (1.0 + (0.004 * revision_index))
                first_mode = part["freq"] * (1.0 - 0.012 * revision_index)
                if part_index == 2 and revision == "Rev C" and load_index == 1:
                    stress = part["allow"] * 1.035
                if part_index == 4 and revision == "Rev C" and load_index == 0:
                    displacement = part["disp_limit"] * 0.94
                if part_index == 1 and revision == "Rev C" and load_index == 1:
                    mass = part["mass"] * 1.115
                if part_index == 5 and revision == "Rev C" and load_index == 1:
                    first_mode = part["freq_min"] * 0.96
                timestamp = now - timedelta(days=(2 - revision_index) * 12 + load_index)
                run_id = (
                    "DEMO-" + str(part_index + 1).zfill(2) + "-R" +
                    str(revision_index + 1) + "-L" + str(load_index + 1)
                )
                runs.append(SimulationRun(
                    run_id=run_id,
                    recorded_at=timestamp,
                    vehicle_program=part["program"],
                    component=part["name"],
                    design_revision=revision,
                    load_case=load_case,
                    solver="OptiStruct (demo)",
                    mesh_elements=42000 + part_index * 5100 + revision_index * 1250 + load_index * 700,
                    mass_kg=round(mass, 3),
                    target_mass_kg=part["mass"],
                    max_stress_mpa=round(stress, 3),
                    allowable_stress_mpa=part["allow"],
                    yield_strength_mpa=part["yield"],
                    max_displacement_mm=round(displacement, 4),
                    allowable_displacement_mm=part["disp_limit"],
                    first_mode_hz=round(first_mode, 3),
                    minimum_mode_hz=part["freq_min"],
                    minimum_safety_factor=1.25,
                ))
    return runs


def seed_database() -> None:
    with connect() as db:
        count = db.execute("SELECT COUNT(*) FROM simulation_runs").fetchone()[0]
        if count:
            return
        demo_runs = make_demo_runs()
        evaluations = evaluate_batch(demo_runs)
        for run, evaluation in zip(demo_runs, evaluations):
            save_run(db, run, evaluation)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    seed_database()
    yield


app = FastAPI(
    title="FEMTrace CAE Validation Workbench",
    version="1.1.0",
    description="A synthetic-data portfolio project for explainable CAE result review and exploratory anomaly triage.",
    lifespan=lifespan,
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "femtrace-api"}


@app.get("/api/summary")
def summary() -> dict[str, Any]:
    with connect() as db:
        totals = db.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
                   SUM(CASE WHEN status = 'REVIEW' THEN 1 ELSE 0 END) AS review,
                   SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) AS failed,
                   AVG(safety_factor) AS avg_safety_factor
            FROM simulation_runs
            """
        ).fetchone()
        open_findings = db.execute(
            "SELECT COUNT(*) FROM findings WHERE status = 'Open'"
        ).fetchone()[0]
        revisions = db.execute(
            """
            SELECT design_revision AS revision, COUNT(*) AS run_count,
                   SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
                   SUM(CASE WHEN status = 'REVIEW' THEN 1 ELSE 0 END) AS review,
                   SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) AS failed
            FROM simulation_runs
            GROUP BY design_revision
            ORDER BY MAX(recorded_at)
            """
        ).fetchall()
        recent = db.execute(
            """
            SELECT run_id, recorded_at, component, design_revision, load_case,
                   solver, status, max_stress_mpa, safety_factor, stress_margin_pct,
                   displacement_margin_pct, finding_count
            FROM simulation_runs ORDER BY recorded_at DESC LIMIT 8
            """
        ).fetchall()
    return {
        "totalRuns": totals["total"] or 0,
        "passed": totals["passed"] or 0,
        "review": totals["review"] or 0,
        "failed": totals["failed"] or 0,
        "openFindings": open_findings,
        "avgSafetyFactor": round(totals["avg_safety_factor"] or 0, 2),
        "evaluationEngine": "C++17" if ENGINE_PATH.is_file() else "Python fallback",
        "revisions": [dict(row) for row in revisions],
        "recentRuns": [dict(row) for row in recent],
    }


@app.get("/api/components")
def components() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT r.component,
                   COUNT(*) AS run_count,
                   MAX(r.recorded_at) AS latest_at,
                   (SELECT x.status FROM simulation_runs x
                    WHERE x.component = r.component
                    ORDER BY x.recorded_at DESC LIMIT 1) AS latest_status,
                   (SELECT x.design_revision FROM simulation_runs x
                    WHERE x.component = r.component
                    ORDER BY x.recorded_at DESC LIMIT 1) AS latest_revision,
                   (SELECT COUNT(*) FROM findings f
                    WHERE f.component = r.component AND f.status = 'Open') AS open_findings
            FROM simulation_runs r
            GROUP BY r.component
            ORDER BY r.component
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/runs")
def runs(
    status: str = Query(default="all", pattern="^(all|PASS|REVIEW|FAIL)$"),
    component: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status != "all":
        clauses.append("status = ?")
        params.append(status)
    if component:
        clauses.append("component = ?")
        params.append(component)
    if search:
        clauses.append("(run_id LIKE ? OR component LIKE ? OR design_revision LIKE ? OR load_case LIKE ?)")
        needle = "%" + search.strip() + "%"
        params.extend([needle, needle, needle, needle])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM simulation_runs" + where +
            " ORDER BY recorded_at DESC LIMIT 500",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM simulation_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found")
        related = db.execute(
            "SELECT * FROM findings WHERE run_id = ? ORDER BY severity DESC, rule_name",
            (run_id,),
        ).fetchall()
    return {**dict(row), "findings": [dict(item) for item in related]}


@app.get("/api/findings")
def findings(status: str = Query(default="Open", pattern="^(all|Open|Resolved)$")) -> list[dict[str, Any]]:
    clause = "" if status == "all" else "WHERE f.status = ?"
    params = [] if status == "all" else [status]
    with connect() as db:
        rows = db.execute(
            """
            SELECT f.*, r.recorded_at, r.solver, r.vehicle_program
            FROM findings f JOIN simulation_runs r ON r.run_id = f.run_id
            """ + clause + """
            ORDER BY CASE f.severity WHEN 'Critical' THEN 0 ELSE 1 END,
                     r.recorded_at DESC
            LIMIT 250
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


AI_FEATURES = [
    ("stress_utilization", "Stress utilization", "% of allowable", "upper"),
    ("displacement_utilization", "Displacement utilization", "% of limit", "upper"),
    ("safety_factor_shortfall", "Safety-factor shortfall", "% of minimum", "upper"),
    ("modal_shortfall", "Modal-frequency shortfall", "% of minimum", "upper"),
    ("mass_deviation_pct", "Mass deviation", "% vs target", "signed"),
]
AI_MIN_SAMPLES = 8


def ai_feature_values(row: sqlite3.Row) -> list[float]:
    return [
        row["max_stress_mpa"] / row["allowable_stress_mpa"] * 100,
        row["max_displacement_mm"] / row["allowable_displacement_mm"] * 100,
        row["minimum_safety_factor"] / row["safety_factor"] * 100,
        row["minimum_mode_hz"] / row["first_mode_hz"] * 100,
        (row["mass_kg"] - row["target_mass_kg"]) / row["target_mass_kg"] * 100,
    ]


@app.get("/api/ai/anomalies")
def ai_anomalies(limit: int = Query(default=16, ge=1, le=100)) -> dict[str, Any]:
    """Fit a transparent, unsupervised triage model to the available run history."""
    with connect() as db:
        rows = db.execute("SELECT * FROM simulation_runs ORDER BY recorded_at DESC").fetchall()
    sample_count = len(rows)
    response: dict[str, Any] = {
        "model": "Isolation Forest",
        "modelVersion": sklearn.__version__,
        "featureNames": [item[1] for item in AI_FEATURES],
        "sampleCount": sample_count,
        "minimumSamples": AI_MIN_SAMPLES,
        "isReady": sample_count >= AI_MIN_SAMPLES,
        "flaggedCount": 0,
        "rows": [],
        "notice": "Exploratory triage only. This model has no labeled failure data and does not assess design safety or certify a component.",
    }
    if sample_count < AI_MIN_SAMPLES:
        response["notice"] = (
            f"Add at least {AI_MIN_SAMPLES - sample_count} more simulation runs to enable exploratory anomaly triage. "
            + response["notice"]
        )
        return response

    matrix = [ai_feature_values(row) for row in rows]
    model = IsolationForest(
        n_estimators=200,
        max_samples=min(256, sample_count),
        contamination="auto",
        random_state=42,
        n_jobs=1,
    )
    model.fit(matrix)
    decision_scores = model.decision_function(matrix)
    predictions = model.predict(matrix)
    worst_first = sorted(range(sample_count), key=lambda idx: (float(decision_scores[idx]), rows[idx]["recorded_at"]))
    anomaly_percentile: dict[int, float] = {}
    if sample_count == 1:
        anomaly_percentile[worst_first[0]] = 100.0
    else:
        for rank, idx in enumerate(worst_first):
            anomaly_percentile[idx] = round((sample_count - rank - 1) / (sample_count - 1) * 100, 1)

    medians: list[float] = []
    deviations: list[float] = []
    for col in range(len(AI_FEATURES)):
        column = sorted(values[col] for values in matrix)
        middle = sample_count // 2
        median = column[middle] if sample_count % 2 else (column[middle - 1] + column[middle]) / 2
        abs_diffs = sorted(abs(value - median) for value in column)
        mad = abs_diffs[middle] if sample_count % 2 else (abs_diffs[middle - 1] + abs_diffs[middle]) / 2
        medians.append(median)
        deviations.append(mad * 1.4826 if mad > 1e-9 else max(abs(median) * 0.05, 1e-6))

    ranked: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        values = matrix[idx]
        drivers = []
        for col, feature in enumerate(AI_FEATURES):
            deviation_mad = abs(values[col] - medians[col]) / deviations[col]
            drivers.append({
                "key": feature[0],
                "label": feature[1],
                "value": round(values[col], 2),
                "unit": feature[2],
                "deviationMad": round(deviation_mad, 2),
            })
        drivers.sort(key=lambda item: item["deviationMad"], reverse=True)
        ranked.append({
            "run_id": row["run_id"],
            "component": row["component"],
            "design_revision": row["design_revision"],
            "load_case": row["load_case"],
            "recorded_at": row["recorded_at"],
            "status": row["status"],
            "anomaly_score": anomaly_percentile[idx],
            "is_anomaly": bool(predictions[idx] == -1),
            "drivers": drivers[:3],
        })
    ranked.sort(key=lambda item: (not item["is_anomaly"], -item["anomaly_score"]))
    response["flaggedCount"] = sum(1 for value in predictions if value == -1)
    response["rows"] = ranked[:limit]
    return response


@app.get("/api/imports")
def import_history(limit: int = Query(default=12, ge=1, le=50)) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM import_batches ORDER BY imported_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/findings/{finding_id}/resolve")
def resolve_finding(finding_id: str) -> dict[str, Any]:
    with connect() as db:
        cursor = db.execute(
            "UPDATE findings SET status = 'Resolved' WHERE finding_id = ?",
            (finding_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Finding not found")
        row = db.execute(
            "SELECT finding_id, status FROM findings WHERE finding_id = ?",
            (finding_id,),
        ).fetchone()
    return dict(row)


@app.post("/api/runs/import")
async def import_runs(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a CSV file")
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(status_code=413, detail="CSV must be smaller than 5 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must use UTF-8 encoding") from exc

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Missing required columns: " + ", ".join(missing),
        )

    parsed: list[SimulationRun] = []
    for line_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            parsed.append(SimulationRun.model_validate(row))
        except ValidationError as exc:
            errors = "; ".join(
                item["loc"][0].__str__() + ": " + item["msg"]
                for item in exc.errors()
            )
            raise HTTPException(
                status_code=422,
                detail="CSV row " + str(line_number) + ": " + errors,
            ) from exc
        if len(parsed) > 10_000:
            raise HTTPException(status_code=413, detail="A single import is limited to 10,000 rows")
    if not parsed:
        raise HTTPException(status_code=400, detail="CSV contains no data rows")

    evaluations = evaluate_batch(parsed)
    inserted = 0
    import_id = str(uuid.uuid4())
    imported_at = datetime.now(timezone.utc).isoformat()
    source_filename = Path(file.filename).name[:255]
    content_sha256 = hashlib.sha256(content).hexdigest()
    with connect() as db:
        for run, evaluation in zip(parsed, evaluations):
            inserted += int(save_run(db, run, evaluation))
        db.execute(
            """
            INSERT INTO import_batches (
                import_id, source_filename, content_sha256, imported_at,
                received_rows, inserted_rows, duplicate_rows, schema_version, evaluator_engine
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id, source_filename, content_sha256, imported_at,
                len(parsed), inserted, len(parsed) - inserted, "1.0",
                "C++17" if ENGINE_PATH.is_file() else "Python fallback",
            ),
        )
    return {
        "importId": import_id,
        "sourceFilename": source_filename,
        "contentSha256": content_sha256,
        "importedAt": imported_at,
        "schemaVersion": "1.0",
        "evaluatorEngine": "C++17" if ENGINE_PATH.is_file() else "Python fallback",
        "received": len(parsed),
        "inserted": inserted,
        "duplicatesSkipped": len(parsed) - inserted,
        "message": "CAE result rows evaluated against the criteria supplied in each row.",
    }


@app.get("/api/template")
def template() -> Any:
    sample = PROJECT_ROOT / "sample_data" / "fea_results_template.csv"
    return FileResponse(sample, filename="fea_results_template.csv", media_type="text/csv")


@app.get("/api/comparisons")
def comparisons(limit: int = Query(default=24, ge=1, le=100)) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM simulation_runs ORDER BY component, load_case, recorded_at"
        ).fetchall()
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault((row["component"], row["load_case"]), []).append(row)
    output: list[dict[str, Any]] = []
    for (component, load_case), sequence in groups.items():
        for previous, current in zip(sequence, sequence[1:]):
            output.append({
                "component": component,
                "load_case": load_case,
                "previous_revision": previous["design_revision"],
                "current_revision": current["design_revision"],
                "recorded_at": current["recorded_at"],
                "stress_delta_pct": round(
                    (current["max_stress_mpa"] - previous["max_stress_mpa"])
                    / previous["max_stress_mpa"] * 100, 2
                ),
                "displacement_delta_pct": round(
                    (current["max_displacement_mm"] - previous["max_displacement_mm"])
                    / max(previous["max_displacement_mm"], 0.0001) * 100, 2
                ),
                "mass_delta_pct": round(
                    (current["mass_kg"] - previous["mass_kg"])
                    / previous["mass_kg"] * 100, 2
                ),
                "previous_status": previous["status"],
                "current_status": current["status"],
            })
    output.sort(key=lambda item: item["recorded_at"], reverse=True)
    return output[:limit]


@app.get("/")
def index() -> Any:
    path = STATIC_DIR / "index.html"
    if path.exists():
        return FileResponse(path)
    return {
        "name": "FEMTrace CAE Validation Workbench",
        "message": "Start the Vite frontend with npm run dev, or build it to serve the app here.",
    }


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")

