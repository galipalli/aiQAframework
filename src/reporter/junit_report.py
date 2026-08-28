"""JUnit XML report output."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.models.test_result import RunResult


def generate_junit_xml(
    run_result: RunResult,
    output_path: Path,
) -> None:
    """Write a JUnit XML report for CI consumption."""
    testsuites = ET.Element("testsuites")

    testsuite = ET.SubElement(
        testsuites,
        "testsuite",
        name=run_result.run_id,
        tests=str(run_result.total_tests),
        failures=str(run_result.failed),
        errors=str(run_result.errors),
        skipped=str(run_result.skipped),
        time=f"{run_result.duration_seconds:.3f}",
    )

    for result in run_result.test_results:
        testcase = ET.SubElement(
            testsuite,
            "testcase",
            name=result.test_name,
            classname=result.category,
            time=f"{result.duration_seconds:.3f}",
        )

        if result.result == "fail":
            failure = ET.SubElement(testcase, "failure")
            if result.failure_reason:
                failure.set("message", result.failure_reason)
                failure.text = result.failure_reason
        elif result.result == "error":
            error = ET.SubElement(testcase, "error")
            if result.failure_reason:
                error.set("message", result.failure_reason)
                error.text = result.failure_reason
        elif result.result == "skip":
            ET.SubElement(testcase, "skipped")

    tree = ET.ElementTree(testsuites)
    ET.indent(tree, space="  ", level=0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
