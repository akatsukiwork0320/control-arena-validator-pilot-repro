"""Offline reproducibility verifier (Python 3 stdlib only, zero dataset files required).

Verifies:
1. SHA-256 digests of all 11 evidence files recorded in RESULTS.json.
2. SHA-256 digests of all 49 distributed frozen code/spec/fixture files recorded in validator_lock.json
   (plus the 11 git-ignored dataset files if fetched locally via `python fetch_selected.py`).
3. SHA-256 digests recorded in review_followup/formatting.json.
4. Sampling-frame CSV hashes and deterministic seed reproduction of selection.json.
5. Execution of all 202 authored synthetic boundary test cases across the 10 validators.
6. Execution of all 30 PR #899 isolated subprocess (`python -I`) boolean adapter interface checks.
7. Cross-runtime agreement between recorded Python 3.12.6 and Python 3.4.10 outputs.
"""
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys

if sys.flags.optimize:
    raise RuntimeError("Offline verification requires assertions; do not use -O or PYTHONOPTIMIZE.")

import pilot

ROOT = os.path.dirname(os.path.abspath(__file__))


def sha256_file(rel_path):
    with open(os.path.join(ROOT, rel_path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_hashes():
    results_meta = pilot.read_json("RESULTS.json")
    for rel_path, expected in sorted(results_meta["evidence_sha256"].items()):
        actual = sha256_file(rel_path)
        assert actual == expected, f"Evidence hash mismatch for {rel_path}: {actual} != {expected}"

    lock = pilot.read_json("validator_lock.json")
    distributed_verified = 0
    dataset_present_verified = 0
    dataset_omitted = 0
    for rel_path, expected in sorted(lock["files"].items()):
        full_path = os.path.join(ROOT, rel_path)
        if rel_path.startswith("problems/") or rel_path.startswith("audit_inputs/"):
            if os.path.exists(full_path):
                actual = sha256_file(rel_path)
                assert actual == expected, f"Dataset file hash mismatch for {rel_path}"
                dataset_present_verified += 1
            else:
                dataset_omitted += 1
        else:
            actual = sha256_file(rel_path)
            assert actual == expected, f"Frozen file hash mismatch for {rel_path}: {actual} != {expected}"
            distributed_verified += 1

    fmt = pilot.read_json("review_followup/formatting.json")
    assert sha256_file("check_formatting.py") == fmt["script_sha256"], "check_formatting.py hash mismatch"
    assert sha256_file("validator_lock.json") == fmt["validator_lock_sha256"], "validator_lock.json hash mismatch"

    return {
        "evidence_files_verified": len(results_meta["evidence_sha256"]),
        "frozen_code_spec_fixture_files_verified": distributed_verified,
        "local_dataset_files_verified": dataset_present_verified,
        "git_omitted_dataset_files": dataset_omitted,
    }


def verify_sampling_selection():
    selection = pilot.read_json("selection.json")
    seed = selection["seed"]
    for source, stratum in selection["strata"].items():
        rel_csv = os.path.join("sampling_frame", f"frame_{source}.csv")
        actual_sha = sha256_file(rel_csv)
        assert actual_sha == stratum["frame_sha256"], f"Frame hash mismatch for {source}"
        with open(os.path.join(ROOT, rel_csv), "rb") as f:
            rows = list(csv.DictReader(f.read().decode("utf-8-sig").splitlines()))
        assert len(rows) == stratum["frame_problems"], f"Frame size mismatch for {source}"
        ranked = sorted(
            rows,
            key=lambda r: hashlib.sha256((seed + "|" + source + "|" + r["problem_id"]).encode("utf-8")).hexdigest(),
        )
        recomputed = [
            {
                "problem_id": r["problem_id"],
                "stored_success_records": int(r["working_" + source + "_records"]),
                "selection_hash": hashlib.sha256((seed + "|" + source + "|" + r["problem_id"]).encode("utf-8")).hexdigest(),
            }
            for r in ranked[:5]
        ]
        assert recomputed == stratum["selected"], f"Recomputed sample mismatch for {source}"
    return {
        "seed": seed,
        "apps_frame_problems": selection["strata"]["apps"]["frame_problems"],
        "control_tax_frame_problems": selection["strata"]["control_tax"]["frame_problems"],
        "selected_problems_verified": 10,
    }


def run_synthetic_fixtures():
    pilot.check_runner()
    total = 0
    failed = 0
    by_status = {"valid": 0, "invalid": 0, "unverified": 0}
    for pid in pilot.selected_ids():
        validate = pilot.load_validator(pid)
        for case in pilot.read_json("tests/cases_" + pid + ".json"):
            res = pilot.classify(validate, case["input"])
            ok = res["status"] == case["expected_status"]
            if "expected_reason" in case:
                ok = ok and res["reason"] == case["expected_reason"]
            total += 1
            by_status[case["expected_status"]] += 1
            if not ok:
                failed += 1
    assert total == 202, f"Expected 202 synthetic cases, ran {total}"
    assert failed == 0, f"{failed} synthetic fixture assertions failed"
    return {"total_fixtures": total, "failed": failed, "by_expected_status": by_status}


def run_adapter_checks():
    total = 0
    failed = 0
    for pid in pilot.selected_ids():
        cases = pilot.read_json("tests/cases_" + pid + ".json")
        selected = {}
        for case in cases:
            selected.setdefault(case["expected_status"], case)
        for state, case in sorted(selected.items()):
            proc = subprocess.Popen(
                [sys.executable, "-I", os.path.join(ROOT, "adapters", "p" + pid + ".py")],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = proc.communicate(case["input"].encode("utf-8"), timeout=10)
            if state in ("valid", "invalid"):
                expected = b"true" if state == "valid" else b"false"
                ok = proc.returncode == 0 and stdout.strip() == expected and not stderr
            else:
                ok = proc.returncode == 2 and not stdout
                ok = ok and json.loads(stderr.decode("utf-8"))["status"] == "unverified"
            total += 1
            if not ok:
                failed += 1
    assert total == 30, f"Expected 30 adapter checks, ran {total}"
    assert failed == 0, f"{failed} adapter checks failed"
    return {"total_adapter_checks": total, "failed": failed}


def verify_cross_runtime_evidence():
    t312 = pilot.read_json("results/tests_py312.json")
    t34 = pilot.read_json("results/tests_py34.json")
    assert t312["counts"] == t34["counts"], "Test counts differ between Python 3.12 and 3.4"
    assert t312["cases"] == t34["cases"], "Test case outcomes differ between Python 3.12 and 3.4"

    a312 = pilot.read_json("results/adapters_py312.json")
    a34 = pilot.read_json("results/adapters_py34.json")
    assert a312["results"] == a34["results"], "Adapter results differ between Python 3.12 and 3.4"

    au312 = pilot.read_json("results/audit_py312.json")
    au34 = pilot.read_json("results/audit_py34.json")
    assert au312["totals"] == au34["totals"] == {"valid": 23, "invalid": 1, "unverified": 0, "error": 0}
    assert au312["records"] == au34["records"], "Audit record outcomes differ between Python 3.12 and 3.4"
    return {
        "recorded_runtimes": [t312["python"], t34["python"]],
        "cross_runtime_identical": True,
        "audit_totals": au312["totals"],
        "normal_inputs_tested": t312["counts"]["recorded_normal_inputs"],
        "normal_statement_conflicts": len(t312["normal_input_nonvalid"]),
    }


def main():
    summary = {
        "current_python": platform.python_version(),
        "hashes": verify_hashes(),
        "sampling_selection": verify_sampling_selection(),
        "synthetic_fixtures": run_synthetic_fixtures(),
        "adapter_subprocess_checks": run_adapter_checks(),
        "cross_runtime_evidence": verify_cross_runtime_evidence(),
        "status": "ALL_OFFLINE_CHECKS_PASSED",
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
