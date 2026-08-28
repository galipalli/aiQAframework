"""Tests for JUnit XML report generation."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.models.test_result import (
    Evidence,
    RunResult,
    TestResult,
)
from src.reporter.junit_report import generate_junit_xml


class TestGenerateJunitXml:
    """Tests for generate_junit_xml function."""

    def _parse_xml(self, path: Path) -> ET.Element:
        with open(path, "rb") as f:
            return ET.parse(f).getroot()

    def test_empty_results(self, tmp_path: Path):
        """Test JUnit XML with no test results."""
        run_result = RunResult(
            run_id="run-empty",
            plan_id="plan-001",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            target_url="https://example.com",
            total_tests=0,
            passed=0,
            failed=0,
            skipped=0,
            errors=0,
            duration_seconds=0.0,
            test_results=[],
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        assert output_file.exists()
        root = self._parse_xml(output_file)
        assert root.tag == "testsuites"
        suite = root.find("testsuite")
        assert suite is not None
        assert suite.get("tests") == "0"
        assert suite.get("failures") == "0"
        assert suite.get("errors") == "0"
        assert suite.get("skipped") == "0"

    def test_all_passed(self, tmp_path: Path):
        """Test JUnit XML with all tests passed."""
        test_results = [
            TestResult(
                test_id="test-001",
                test_name="Login Test",
                category="functional",
                result="pass",
                duration_seconds=1.5,
            ),
            TestResult(
                test_id="test-002",
                test_name="Checkout Test",
                category="functional",
                result="pass",
                duration_seconds=2.3,
            ),
        ]

        run_result = RunResult(
            run_id="run-pass",
            plan_id="plan-002",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:05:00Z",
            target_url="https://example.com",
            total_tests=2,
            passed=2,
            failed=0,
            skipped=0,
            errors=0,
            duration_seconds=10.0,
            test_results=test_results,
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        root = self._parse_xml(output_file)
        suite = root.find("testsuite")
        assert suite.get("tests") == "2"
        assert suite.get("failures") == "0"
        assert suite.get("errors") == "0"

        cases = suite.findall("testcase")
        assert len(cases) == 2
        assert cases[0].get("name") == "Login Test"
        assert cases[0].get("classname") == "functional"
        assert cases[0].get("time") == "1.500"
        assert cases[1].get("name") == "Checkout Test"
        assert cases[1].get("time") == "2.300"

        assert cases[0].find("failure") is None
        assert cases[0].find("error") is None
        assert cases[0].find("skipped") is None

    def test_failures(self, tmp_path: Path):
        """Test JUnit XML with failing tests."""
        test_results = [
            TestResult(
                test_id="test-001",
                test_name="Failing Test",
                category="functional",
                result="fail",
                duration_seconds=0.5,
                failure_reason="AssertionError: expected 200 but got 500",
            ),
        ]

        run_result = RunResult(
            run_id="run-fail",
            plan_id="plan-003",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            target_url="https://example.com",
            total_tests=1,
            passed=0,
            failed=1,
            skipped=0,
            errors=0,
            duration_seconds=5.0,
            test_results=test_results,
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        root = self._parse_xml(output_file)
        suite = root.find("testsuite")
        assert suite.get("failures") == "1"

        case = suite.find("testcase")
        assert case.get("name") == "Failing Test"
        failure = case.find("failure")
        assert failure is not None
        assert failure.get("message") == "AssertionError: expected 200 but got 500"
        assert failure.text == "AssertionError: expected 200 but got 500"

    def test_errors(self, tmp_path: Path):
        """Test JUnit XML with test errors."""
        test_results = [
            TestResult(
                test_id="test-001",
                test_name="Error Test",
                category="security",
                result="error",
                duration_seconds=0.3,
                failure_reason="ConnectionError: timeout",
            ),
        ]

        run_result = RunResult(
            run_id="run-error",
            plan_id="plan-004",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            target_url="https://example.com",
            total_tests=1,
            passed=0,
            failed=0,
            skipped=0,
            errors=1,
            duration_seconds=3.0,
            test_results=test_results,
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        root = self._parse_xml(output_file)
        suite = root.find("testsuite")
        assert suite.get("errors") == "1"

        case = suite.find("testcase")
        error = case.find("error")
        assert error is not None
        assert error.get("message") == "ConnectionError: timeout"
        assert error.text == "ConnectionError: timeout"

    def test_skipped_tests(self, tmp_path: Path):
        """Test JUnit XML with skipped tests."""
        test_results = [
            TestResult(
                test_id="test-001",
                test_name="Skipped Test",
                category="visual",
                result="skip",
                duration_seconds=0.0,
            ),
        ]

        run_result = RunResult(
            run_id="run-skip",
            plan_id="plan-005",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            target_url="https://example.com",
            total_tests=1,
            passed=0,
            failed=0,
            skipped=1,
            errors=0,
            duration_seconds=1.0,
            test_results=test_results,
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        root = self._parse_xml(output_file)
        suite = root.find("testsuite")
        assert suite.get("skipped") == "1"

        case = suite.find("testcase")
        skipped = case.find("skipped")
        assert skipped is not None

    def test_multi_test_case_output(self, tmp_path: Path):
        """Test JUnit XML with mixed test results."""
        test_results = [
            TestResult(
                test_id="test-001",
                test_name="Test A",
                category="functional",
                result="pass",
                duration_seconds=1.0,
            ),
            TestResult(
                test_id="test-002",
                test_name="Test B",
                category="functional",
                result="fail",
                duration_seconds=0.5,
                failure_reason="Element not found",
            ),
            TestResult(
                test_id="test-003",
                test_name="Test C",
                category="security",
                result="error",
                duration_seconds=0.2,
                failure_reason="XSS payload not blocked",
            ),
            TestResult(
                test_id="test-004",
                test_name="Test D",
                category="visual",
                result="skip",
                duration_seconds=0.0,
            ),
        ]

        run_result = RunResult(
            run_id="run-multi",
            plan_id="plan-006",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:05:00Z",
            target_url="https://example.com",
            total_tests=4,
            passed=1,
            failed=1,
            skipped=1,
            errors=1,
            duration_seconds=20.0,
            test_results=test_results,
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        root = self._parse_xml(output_file)
        suite = root.find("testsuite")
        assert suite.get("tests") == "4"
        assert suite.get("failures") == "1"
        assert suite.get("errors") == "1"
        assert suite.get("skipped") == "1"
        assert suite.get("time") == "20.000"

        cases = suite.findall("testcase")
        assert len(cases) == 4

        assert cases[0].get("name") == "Test A"
        assert cases[0].get("classname") == "functional"
        assert cases[0].find("failure") is None
        assert cases[0].find("error") is None

        assert cases[1].get("name") == "Test B"
        assert cases[1].find("failure") is not None

        assert cases[2].get("name") == "Test C"
        assert cases[2].find("error") is not None

        assert cases[3].get("name") == "Test D"
        assert cases[3].find("skipped") is not None

    def test_creates_parent_directory(self, tmp_path: Path):
        """Test report creation creates parent directories."""
        output_file = tmp_path / "subdir" / "nested" / "report.xml"

        run_result = RunResult(
            run_id="run-mkdir",
            plan_id="plan-007",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            target_url="https://example.com",
            total_tests=1,
            passed=1,
        )

        generate_junit_xml(run_result, output_file)

        assert output_file.exists()
        assert output_file.parent.exists()

    def test_xml_escaping(self, tmp_path: Path):
        """Test XML special characters are properly escaped."""
        test_results = [
            TestResult(
                test_id="test-001",
                test_name='Test with "quotes" & <special> chars',
                category="functional",
                result="fail",
                duration_seconds=0.1,
                failure_reason="Expected <div> but got <span>",
            ),
        ]

        run_result = RunResult(
            run_id="run-escape",
            plan_id="plan-008",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            target_url="https://example.com",
            total_tests=1,
            passed=0,
            failed=1,
            duration_seconds=1.0,
            test_results=test_results,
        )

        output_file = tmp_path / "report.xml"
        generate_junit_xml(run_result, output_file)

        root = self._parse_xml(output_file)
        case = root.find("testsuite").find("testcase")
        assert case.get("name") == 'Test with "quotes" & <special> chars'
        failure = case.find("failure")
        assert failure is not None
        assert failure.text == "Expected <div> but got <span>"
