"""Smoke-test Pydantic Evals span-based capture with Sensei.

This script:
1. Loads a small YAML dataset from `sensei/eval/datasets/`.
2. Runs the Sensei PydanticAI agent for each case via Pydantic Evals.
3. Prints the full OpenTelemetry span tree per case.

No quality evaluators/metrics are defined yet; this is only to verify that
spans are captured and accessible to span-based evaluators.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

try:
    import logfire
except ImportError:  # pragma: no cover
    logfire = None

from pydantic_evals import Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from sensei.eval.datasets import load_dataset
from sensei.eval.task import run_agent

LOG_LEVEL = logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

DATASET_NAME = "general"


@dataclass
class PrintSpans(Evaluator[str, str, Any]):
    """Span-based evaluator that prints the full span tree.

    Always returns True; used only for debugging span capture.
    """

    def evaluate(self, ctx: EvaluatorContext[str, str, Any]) -> bool:
        span_tree = ctx.span_tree
        if span_tree is None:
            print("\n=== No spans captured for case ===")
            return True

        print(f"\n=== Spans for case: {ctx.case.name or 'unnamed'} ===")

        for node in span_tree:
            indent = "  " * len(node.ancestors)
            duration = node.duration
            attrs = dict(node.attributes or {})
            print(f"{indent}- {node.name} ({duration})")
            if attrs:
                print(f"{indent}  attributes: {attrs}")

        return True


def main() -> None:
    if logfire is not None:
        # Configure local tracing capture without sending to Logfire.
        logfire.configure(send_to_logfire=False)

    base_dataset = load_dataset(DATASET_NAME)
    dataset = Dataset(cases=base_dataset.cases[:2], evaluators=[PrintSpans()])

    report = dataset.evaluate_sync(run_agent)
    report.print(include_input=True, include_output=False, include_durations=False)


if __name__ == "__main__":
    main()
