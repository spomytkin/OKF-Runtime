"""CLI for OKF Runtime evaluations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .baseline import compare_results, load_baseline
from .cases import default_cases_path, filter_cases, load_cases, validate_cases
from .runner import RunnerError, run_and_write


def _repo_root() -> Path:
    return Path.cwd()


def cmd_cases_validate(args: argparse.Namespace) -> int:
    path = Path(args.cases) if args.cases else default_cases_path(_repo_root())
    try:
        cases = load_cases(path)
    except (OSError, ValueError) as exc:
        print(f"Invalid case data: {exc}", file=sys.stderr)
        return 2
    errors = validate_cases(cases)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print(f"Validated {len(cases)} cases from {path}")
    return 0


def cmd_cases_list(args: argparse.Namespace) -> int:
    path = Path(args.cases) if args.cases else default_cases_path(_repo_root())
    try:
        cases = filter_cases(load_cases(path), suite=args.suite, tags=set(args.tags or []))
    except (OSError, ValueError) as exc:
        print(f"Invalid case data: {exc}", file=sys.stderr)
        return 2
    for case in cases:
        print(f"{case.id}\t{case.suite}\t{case.description}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.cases) if args.cases else default_cases_path(_repo_root())
    try:
        cases = filter_cases(load_cases(path), suite=args.suite, tags=set(args.tags or []))
    except (OSError, ValueError) as exc:
        print(f"Invalid case data: {exc}", file=sys.stderr)
        return 2
    errors = validate_cases(cases)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    output = Path(args.output)
    try:
        result = run_and_write(
            cases,
            repo_root=_repo_root(),
            output_path=output,
            adapter=args.adapter,
            adapter_target=args.target or args.command or args.url,
            run_name=args.run_name,
        )
    except (RunnerError, ValueError) as exc:
        print(f"Invalid eval configuration: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - unexpected execution failure
        print(f"Evaluation execution failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"run_id": result.run_id, "gates_passed": result.gates.get("passed"), "output": str(output)}, indent=2))
    return 0 if result.gates.get("passed") else 1


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        current = json.loads(Path(args.current).read_text(encoding="utf-8"))
        baseline = load_baseline(Path(args.baseline))
        comparison = compare_results(current, baseline)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Invalid result or baseline data: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(comparison, indent=2))
    return 0 if comparison["passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="okf_runtime.evals.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    cases = sub.add_parser("cases")
    cases_sub = cases.add_subparsers(dest="cases_command", required=True)

    validate = cases_sub.add_parser("validate")
    validate.add_argument("--cases", default=None)
    validate.set_defaults(func=cmd_cases_validate)

    list_cmd = cases_sub.add_parser("list")
    list_cmd.add_argument("--cases", default=None)
    list_cmd.add_argument("--suite", default=None)
    list_cmd.add_argument("--tags", nargs="*", default=None)
    list_cmd.set_defaults(func=cmd_cases_list)

    run = sub.add_parser("run")
    run.add_argument("--cases", default=None)
    run.add_argument("--suite", default=None)
    run.add_argument("--tags", nargs="*", default=None)
    run.add_argument("--adapter", default="reference", choices=["reference", "callable", "subprocess", "http"])
    run.add_argument("--target", default=None, help="Callable dotted path for --adapter callable")
    run.add_argument("--command", default=None, help="Subprocess command string for --adapter subprocess")
    run.add_argument("--url", default=None, help="HTTP endpoint for --adapter http")
    run.add_argument("--output", default=".evals/results.json")
    run.add_argument("--run-name", default=None)
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare")
    compare.add_argument("current")
    compare.add_argument("--baseline", required=True)
    compare.set_defaults(func=cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
