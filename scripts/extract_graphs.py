"""Extract one C function into Graph A and Graph B Tier-1 JSON records.

This command deliberately accepts one explicit source file and function. It
does not read a manifest or discover dataset files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.joern import JoernConfig, JoernExecutionError, JoernExtractor  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402

LOGGER = get_logger("extract_graphs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract one explicit C function to Graph A/B Tier-1 JSON."
    )
    parser.add_argument("--source", type=Path, required=True, help="Standalone C source file")
    parser.add_argument("--function", required=True, help="Exact Joern method name")
    parser.add_argument("--sample-id", required=True, help="Safe identifier used in output filenames")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--schema-config",
        type=Path,
        default=ROOT / "configs" / "graph" / "schema_spec.yaml",
        help="Graph schema configuration containing size warning thresholds",
    )
    parser.add_argument("--joern", default="joern")
    parser.add_argument("--joern-parse", default="joern-parse")
    parser.add_argument("--java-home", help="Process-local JDK 21 home; defaults to $HOME/jdk/jdk-21 in WSL")
    parser.add_argument("--wsl-distro", default="Ubuntu")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--cwe", help="Copy an explicitly supplied raw CWE value")
    parser.add_argument("--project-wise-split")
    parser.add_argument("--seen-project-split")
    parser.add_argument("--project-name", help="Redaction context only; never serialized")
    parser.add_argument("--commit-id", help="Redaction context only; never serialized")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        schema = load_config(args.schema_config)
        limits = schema.get("size_limits", {})
        extractor = JoernExtractor(
            JoernConfig(
                executable=args.joern,
                parse_executable=args.joern_parse,
                java_home=args.java_home,
                wsl_distro=args.wsl_distro,
                timeout_sec=args.timeout,
                max_nodes=int(limits.get("max_nodes", 1000)),
                max_edges=int(limits.get("max_edges", 3000)),
            )
        )
        result = extractor.extract(
            args.source,
            args.output_dir,
            sample_id=args.sample_id,
            function_name=args.function,
            cwe=args.cwe,
            project_wise_split=args.project_wise_split,
            seen_project_split=args.seen_project_split,
            project_name=args.project_name,
            commit_id=args.commit_id,
        )
    except (FileNotFoundError, ValueError, JoernExecutionError) as error:
        LOGGER.error("%s", error)
        return 1

    print(json.dumps(result.report, ensure_ascii=False, indent=2))
    print(f"Graph A: {result.graph_a_path}")
    print(f"Graph B: {result.graph_b_path}")
    print(f"Metrics: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
