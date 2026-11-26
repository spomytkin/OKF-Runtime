"""Command line interface for OKF Runtime."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from . import api


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_command(args)
    except (FileNotFoundError, KeyError, NotADirectoryError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(format_output(result, args.format))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="okf", description="Deterministic runtime for OKF bundles.")
    parser.add_argument("--root", default=".", help="Bundle root or scan root.")
    parser.add_argument("--cache-dir", help="Cache directory (defaults to <root>/.cache).")
    parser.add_argument("--format", choices=["json", "yaml"], default="json", help="Output format.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("discover")

    catalog_parser = subparsers.add_parser("catalog")
    catalog_parser.add_argument("--verbose", action="store_true", help="Include links and backlinks.")
    catalog_parser.add_argument("--short", action="store_true", help="Only include id, path, type, and title.")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("filters", nargs="*", help="Metadata filters as key=value.")
    query_parser.add_argument("--via", action="append", default=[], metavar="KEY=VALUE", help="Filter nested list-of-mapping metadata.")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("concept_id")
    show_parser.add_argument("--body", action="store_true", help="Include markdown body.")

    links_parser = subparsers.add_parser("links")
    links_parser.add_argument("concept_id", nargs="?")

    backlinks_parser = subparsers.add_parser("backlinks")
    backlinks_parser.add_argument("concept_id", nargs="?")

    graph_parser = subparsers.add_parser("graph")
    graph_parser.add_argument("concept_id")
    graph_parser.add_argument("--depth", type=int, default=1)
    graph_parser.add_argument("--resolve-resources", action="store_true")

    compose_parser = subparsers.add_parser("compose")
    compose_parser.add_argument("topic")
    compose_parser.add_argument("--output-dir")
    compose_parser.add_argument("--depth", type=int, default=1)
    compose_parser.add_argument("--min-trust", choices=["unverified", "machine-confirmed", "human-reviewed"])
    compose_parser.add_argument("--resolve-resources", action="store_true")

    trust_parser = subparsers.add_parser("trust")
    trust_parser.add_argument("concept_id", nargs="?")

    subparsers.add_parser("lint-links")
    subparsers.add_parser("verify-sources")
    return parser


def run_command(args: argparse.Namespace) -> Any:
    if args.command == "discover":
        return api.discover(args.root)
    if args.command == "catalog":
        records = api.catalog(args.root, include_links=args.verbose, cache_dir=args.cache_dir)
        return short_catalog(records) if args.short else records
    if args.command == "query":
        return api.query(args.root, cache_dir=args.cache_dir, **parse_filters(args.filters + args.via))
    if args.command == "show":
        return api.show(args.root, args.concept_id, include_body=args.body, cache_dir=args.cache_dir)
    if args.command == "links":
        return api.links(args.root, args.concept_id, cache_dir=args.cache_dir)
    if args.command == "backlinks":
        return api.backlinks(args.root, args.concept_id, cache_dir=args.cache_dir)
    if args.command == "graph":
        return api.graph(args.root, args.concept_id, depth=args.depth, resolve_resources=args.resolve_resources, cache_dir=args.cache_dir)
    if args.command == "compose":
        return api.compose(args.root, args.topic, output_dir=args.output_dir, depth=args.depth, min_trust=args.min_trust, resolve_resources=args.resolve_resources, cache_dir=args.cache_dir)
    if args.command == "trust":
        return api.trust(args.root, args.concept_id, cache_dir=args.cache_dir)
    if args.command == "lint-links":
        return api.lint_links(args.root, cache_dir=args.cache_dir)
    if args.command == "verify-sources":
        return api.verify_sources(args.root, cache_dir=args.cache_dir)
    raise ValueError(f"Unknown command: {args.command}")


def parse_filters(filters: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in filters:
        if "=" not in item:
            raise ValueError(f"Invalid filter {item!r}; expected key=value")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def short_catalog(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": record["id"],
            "path": record["path"],
            "type": record["metadata"].get("type"),
            "title": record["metadata"].get("title"),
            **({"okf_version": record["okf_version"]} if "okf_version" in record else {}),
        }
        for record in records
    ]


def format_output(value: Any, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(value, indent=2, sort_keys=True)
    return dump_yaml(value)


def dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {format_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                rendered = dump_yaml(item, indent + 2).splitlines()
                if rendered:
                    lines.append(f"{prefix}- {rendered[0].lstrip()}")
                    lines.extend(f"{prefix}  {line}" for line in rendered[1:])
                else:
                    lines.append(f"{prefix}-")
            else:
                lines.append(f"{prefix}- {format_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{format_scalar(value)}"


def format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text or any(char in text for char in [":", "#", "\n", "{", "}", "[", "]"]):
        return json.dumps(text)
    return text


if __name__ == "__main__":
    raise SystemExit(main())
