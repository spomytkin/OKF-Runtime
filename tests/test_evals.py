from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from okf_runtime.evals.adapters.http import HttpAdapterError, invoke_http
from okf_runtime.evals.adapters.subprocess import SubprocessAdapterError, invoke_subprocess
from okf_runtime.evals.baseline import compare_results, evaluate_gates, normalize_for_compare
from okf_runtime.evals.cases import default_cases_path, load_cases, validate_cases
from okf_runtime.evals.cli import main as eval_cli_main
from okf_runtime.evals.config import EvalConfig
from okf_runtime.evals.redaction import redact_value
from okf_runtime.evals.reporters.langfuse import LangfuseReporter
from okf_runtime.evals.runner import _case_request, _invoke_with_timeout, run_cases
from okf_runtime.evals.schema import PROTOCOL_VERSION, SubjectRequest, SubjectResponse
from okf_runtime.evals.scoring import score_case


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeHTTPResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body

class FakeObservation:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, **kwargs):
        self.output = kwargs.get("output")


class FakeLangfuseClient:
    def __init__(self):
        self.scores = []
        self.flushed = False

    def start_as_current_observation(self, **kwargs):
        self.observation_kwargs = kwargs
        return FakeObservation()

    def get_current_trace_id(self):
        return "trace-1"

    def create_score(self, **kwargs):
        self.scores.append(kwargs)

    def flush(self):
        self.flushed = True



class EvalSchemaTests(unittest.TestCase):
    def test_cases_validate(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))
        errors = validate_cases(cases)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(cases), 20)


class EvalScoringTests(unittest.TestCase):
    def test_not_applicable_aggregation(self) -> None:
        case = load_cases(default_cases_path(REPO_ROOT))[0]
        response = SubjectResponse(
            protocol_version=PROTOCOL_VERSION,
            case_id=case.id,
            status="ok",
            output={"structured": {"discover": [{"markdown_files": 1}]}},
            events=[{"type": "tool_call", "name": "okf.discover", "arguments": {}, "result": []}],
        )
        scores = score_case(case, response, source_unchanged=True)
        replay = next(score for score in scores if score.name == "deterministic_replay")
        self.assertFalse(replay.applicable)

    def test_redaction(self) -> None:
        payload = {"token": "sk-1234567890abcdef", "note": "api_key=secret-value"}
        redacted = redact_value(payload)
        self.assertNotIn("secret-value", str(redacted))


class EvalRunnerTests(unittest.TestCase):
    def test_reference_suite_passes(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))
        result = run_cases(cases, repo_root=REPO_ROOT, adapter="reference", config=EvalConfig(False, None, None, None))
        self.assertTrue(result.gates["passed"])
        self.assertEqual(result.metadata["case_count"], len(cases))

    def test_one_bad_case_does_not_abort(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))
        error_case = next(case for case in cases if case.id == "runtime.error.unknown_concept")
        subset = cases[:2] + [error_case]
        result = run_cases(
            subset,
            repo_root=REPO_ROOT,
            adapter="reference",
            config=EvalConfig(False, None, None, None),
        )
        self.assertEqual(len(result.cases), 3)
        by_id = {case.case_id: case for case in result.cases}
        self.assertEqual(by_id[error_case.id].status, "error")
        self.assertEqual(by_id[error_case.id].gate_status, "ok")

    def test_external_subject_request_does_not_expose_plan(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))
        request = _case_request(cases[0], REPO_ROOT / cases[0].fixture)
        self.assertNotIn("plan", request.metadata)

    def test_subject_exception_isolated(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))

        def subject(request):
            raise RuntimeError("boom")

        response = _invoke_with_timeout(
            subject,
            SubjectRequest(PROTOCOL_VERSION, cases[0].id, {}, {}, {}),
            1,
        )
        self.assertEqual(response.status, "error")
        self.assertIn("boom", response.error or "")

    def test_response_size_limit(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))
        result = run_cases(
            [cases[0]],
            repo_root=REPO_ROOT,
            adapter="reference",
            config=EvalConfig(False, None, None, None, max_response_bytes=1),
        )
        self.assertEqual(result.cases[0].status, "invalid")
        self.assertEqual(result.cases[0].error_category, "invalid")


class EvalAdapterTests(unittest.TestCase):
    def test_subprocess_round_trip(self) -> None:
        case = load_cases(default_cases_path(REPO_ROOT))[0]
        request = SubjectRequest(
            protocol_version=PROTOCOL_VERSION,
            case_id=case.id,
            input=case.input,
            context={"bundle_root": str((REPO_ROOT / case.fixture).resolve())},
            metadata={"plan": case.plan, "timeout_seconds": 30},
        )
        command = [sys.executable, "-B", str(REPO_ROOT / "scripts" / "eval_reference_subject.py")]
        response = invoke_subprocess(command, request, timeout_seconds=30)
        self.assertEqual(response.status, "ok")

    def test_http_malformed_json(self) -> None:
        request = SubjectRequest(
            protocol_version=PROTOCOL_VERSION,
            case_id="x",
            input={"prompt": "x"},
            context={"bundle_root": str(REPO_ROOT)},
        )
        with patch("urllib.request.urlopen", return_value=FakeHTTPResponse(b"not-json")):
            with self.assertRaises(HttpAdapterError):
                invoke_http("http://example.invalid", request, timeout_seconds=5)

    def test_http_error_isolated(self) -> None:
        request = SubjectRequest(
            protocol_version=PROTOCOL_VERSION,
            case_id="x",
            input={"prompt": "x"},
            context={"bundle_root": str(REPO_ROOT)},
        )
        error = urllib.error.HTTPError(
            "http://example.invalid",
            500,
            "server error",
            {},
            io.BytesIO(b"bad"),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(HttpAdapterError):
                invoke_http("http://example.invalid", request, timeout_seconds=5)

    def test_invalid_subject_response_type_is_isolated(self) -> None:
        cases = load_cases(default_cases_path(REPO_ROOT))
        response = _invoke_with_timeout(lambda request: {"not": "a SubjectResponse"}, SubjectRequest(
            PROTOCOL_VERSION, cases[0].id, {}, {}, {}
        ), 1)
        self.assertEqual(response.status, "invalid")
        self.assertIn("unsupported response type", response.error or "")

    def test_run_missing_adapter_target_is_invalid_configuration(self) -> None:
        self.assertEqual(eval_cli_main(["run", "--adapter", "subprocess"]), 2)

    def test_subprocess_malformed_json(self) -> None:
        request = SubjectRequest(
            protocol_version=PROTOCOL_VERSION,
            case_id="x",
            input={"prompt": "x"},
            context={"bundle_root": str(REPO_ROOT)},
            metadata={"timeout_seconds": 5},
        )
        with self.assertRaises(SubprocessAdapterError):
            invoke_subprocess([sys.executable, "-c", "print('not-json')"], request, timeout_seconds=5)


class EvalLangfuseTests(unittest.TestCase):
    def test_publish_with_fake_client(self) -> None:
        client = FakeLangfuseClient()
        reporter = LangfuseReporter(client, EvalConfig(True, "pk", "sk", "http://localhost"))
        from okf_runtime.evals.schema import CaseRunResult, EvalRunResult, ScoreResult

        result = EvalRunResult(
            result_schema_version="1",
            run_id="run",
            run_name="test",
            adapter="reference",
            started_at="t0",
            finished_at="t1",
            cases=[
                CaseRunResult(
                    case_id="runtime.discover.samples",
                    suite="runtime",
                    status="ok",
                    scores=[ScoreResult("task_success", True, "boolean", True, True)],
                    latency_ms=1.0,
                    subject_response={"output": {"answer": "ok"}},
                )
            ],
            aggregates={},
            gates={"passed": True, "checks": {}},
            publication={},
        )
        status = reporter.publish(result)
        self.assertEqual(status["status"], "published")
        self.assertTrue(client.flushed)
        self.assertEqual(client.scores[0]["trace_id"], "trace-1")


class EvalBaselineTests(unittest.TestCase):
    def test_gate_direction(self) -> None:
        aggregates = {
            "source_unchanged": {"applicable": True, "pass_rate": 1.0},
            "protocol_valid": {"applicable": True, "pass_rate": 1.0},
            "result_correctness": {"applicable": True, "mean": 1.0},
        }
        gates = evaluate_gates(aggregates, [{"status": "ok"}], {"source_unchanged_pass_rate": 1.0, "protocol_valid_pass_rate": 1.0, "result_correctness_mean": 1.0, "case_error_count_max": 0})
        self.assertTrue(gates["passed"])

    def test_normalized_compare(self) -> None:
        current = {"run_id": "a", "started_at": "1", "gates": {"checks": {"x": {"passed": False}}}}
        baseline = {"run_id": "b", "started_at": "2", "gates": {"checks": {"x": {"passed": True}}}}
        normalized = normalize_for_compare(current)
        self.assertNotIn("run_id", normalized)
        self.assertFalse(compare_results(current, baseline)["passed"])


if __name__ == "__main__":
    unittest.main()
