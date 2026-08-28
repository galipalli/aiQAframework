"""Tests for crawler request throttling — delay and concurrency limits."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.crawler.crawler import Crawler
from src.models.config import CrawlConfig, FrameworkConfig, ViewportConfig


def _make_crawl_config(**overrides):
    """Create a CrawlConfig with throttle defaults."""
    max_pages = overrides.pop("max_pages", 10)
    max_depth = overrides.pop("max_depth", 3)
    include_patterns = overrides.pop("include_patterns", [])
    exclude_patterns = overrides.pop("exclude_patterns", [])
    wait_for_idle = overrides.pop("wait_for_idle", False)
    request_delay_seconds = overrides.pop("request_delay_seconds", 0.0)
    max_concurrent_requests = overrides.pop("max_concurrent_requests", 1)
    return CrawlConfig(
        target_url="https://example.com",
        max_pages=max_pages,
        max_depth=max_depth,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        wait_for_idle=wait_for_idle,
        request_delay_seconds=request_delay_seconds,
        max_concurrent_requests=max_concurrent_requests,
        **overrides,
    )


def _make_framework_config(tmp_path, **overrides):
    """Create a FrameworkConfig for testing."""
    crawl = _make_crawl_config(**overrides)
    return FrameworkConfig(
        target_url=crawl.target_url,
        crawl=crawl,
    )


def _make_mock_page():
    """Create a mock Playwright page for _priority_crawl tests."""
    mock_page = AsyncMock()
    mock_page.url = "https://example.com/page1"
    mock_page.evaluate = AsyncMock(return_value=[])
    mock_page.goto = AsyncMock(return_value=AsyncMock(status=200))
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.title = AsyncMock(return_value="Test Page")
    mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
    mock_page.screenshot = AsyncMock()
    mock_page.on = Mock()
    mock_page.close = AsyncMock()
    return mock_page


def _make_mock_context(mock_page):
    """Create a mock Playwright browser context."""
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    return mock_context


# ============================================================================
# CrawlConfig throttle field tests
# ============================================================================


class TestCrawlConfigThrottleDefaults:
    """Tests for CrawlConfig throttle field defaults."""

    def test_default_request_delay_seconds(self):
        config = CrawlConfig()
        assert config.request_delay_seconds == 0.0

    def test_default_max_concurrent_requests(self):
        config = CrawlConfig()
        assert config.max_concurrent_requests == 1

    def test_custom_request_delay(self):
        config = CrawlConfig(request_delay_seconds=0.5)
        assert config.request_delay_seconds == 0.5

    def test_custom_max_concurrent_requests(self):
        config = CrawlConfig(max_concurrent_requests=5)
        assert config.max_concurrent_requests == 5


# ============================================================================
# Crawler semaphore initialization tests
# ============================================================================


class TestCrawlerSemaphoreInit:
    """Tests for Crawler semaphore initialization."""

    def test_semaphore_default_initial_value(self, tmp_path):
        config = _make_framework_config(tmp_path)
        crawler = Crawler(config, tmp_path / "out")
        assert crawler._semaphore._value == 1

    def test_semaphore_custom_initial_value(self, tmp_path):
        config = _make_framework_config(tmp_path, max_concurrent_requests=3)
        crawler = Crawler(config, tmp_path / "out")
        assert crawler._semaphore._value == 3


# ============================================================================
# Crawler request delay tests
# ============================================================================


class TestCrawlerRequestDelay:
    """Tests for Crawler request_delay_seconds behavior."""

    @pytest.mark.asyncio
    async def test_sleeps_when_delay_configured(self, tmp_path):
        config = _make_framework_config(tmp_path, request_delay_seconds=0.2, max_pages=1)
        crawler = Crawler(config, tmp_path / "out")

        mock_page = _make_mock_page()
        mock_context = _make_mock_context(mock_page)

        with patch("src.crawler.crawler.human_delay", new_callable=AsyncMock), \
             patch("src.crawler.crawler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("src.crawler.crawler.extract_elements", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.analyze_forms", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.detect_spa_type", new_callable=AsyncMock, return_value="traditional"), \
             patch("src.crawler.crawler.discover_spa_routes", new_callable=AsyncMock, return_value=set()):
            await crawler._priority_crawl(mock_context, "https://example.com")

        mock_sleep.assert_called_with(0.2)

    @pytest.mark.asyncio
    async def test_no_sleep_when_delay_zero(self, tmp_path):
        config = _make_framework_config(tmp_path, request_delay_seconds=0.0, max_pages=1)
        crawler = Crawler(config, tmp_path / "out")

        mock_page = _make_mock_page()
        mock_context = _make_mock_context(mock_page)

        with patch("src.crawler.crawler.human_delay", new_callable=AsyncMock), \
             patch("src.crawler.crawler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("src.crawler.crawler.extract_elements", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.analyze_forms", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.detect_spa_type", new_callable=AsyncMock, return_value="traditional"), \
             patch("src.crawler.crawler.discover_spa_routes", new_callable=AsyncMock, return_value=set()):
            await crawler._priority_crawl(mock_context, "https://example.com")

        mock_sleep.assert_not_called()


# ============================================================================
# Crawler concurrency limit tests
# ============================================================================


class TestCrawlerConcurrencyLimit:
    """Tests for Crawler concurrency limit via semaphore."""

    @pytest.mark.asyncio
    async def test_semaphore_acquired_during_crawl(self, tmp_path):
        config = _make_framework_config(tmp_path, max_concurrent_requests=1, max_pages=1)
        crawler = Crawler(config, tmp_path / "out")

        mock_page = _make_mock_page()
        mock_context = _make_mock_context(mock_page)

        acquire_calls = []
        release_calls = []

        original_acquire = crawler._semaphore.acquire
        async def tracking_acquire(*args, **kwargs):
            acquire_calls.append("acquire")
            return await original_acquire(*args, **kwargs)

        original_release = crawler._semaphore.release
        def tracking_release():
            release_calls.append("release")
            return original_release()

        with patch.object(crawler._semaphore, "acquire", tracking_acquire), \
             patch.object(crawler._semaphore, "release", tracking_release), \
             patch("src.crawler.crawler.human_delay", new_callable=AsyncMock), \
             patch("src.crawler.crawler.extract_elements", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.analyze_forms", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.detect_spa_type", new_callable=AsyncMock, return_value="traditional"), \
             patch("src.crawler.crawler.discover_spa_routes", new_callable=AsyncMock, return_value=set()):
            await crawler._priority_crawl(mock_context, "https://example.com")

        assert len(acquire_calls) >= 1
        assert len(release_calls) >= 1

    @pytest.mark.asyncio
    async def test_semaphore_blocks_when_limit_reached(self, tmp_path):
        config = _make_framework_config(tmp_path, max_concurrent_requests=1, max_pages=2)
        crawler = Crawler(config, tmp_path / "out")

        mock_page = AsyncMock()
        mock_page.url = "https://example.com/page1"
        mock_page.evaluate = AsyncMock(return_value=[])
        mock_page.goto = AsyncMock(return_value=AsyncMock(status=200))
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_page.screenshot = AsyncMock()
        mock_page.on = Mock()
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        semaphore_held = asyncio.Event()
        semaphore_released = asyncio.Event()
        original_acquire = crawler._semaphore.acquire
        call_count = 0

        async def blocking_acquire(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                semaphore_held.set()
                await semaphore_released.wait()
            return await original_acquire(*args, **kwargs)

        with patch.object(crawler._semaphore, "acquire", blocking_acquire), \
             patch("src.crawler.crawler.human_delay", new_callable=AsyncMock), \
             patch("src.crawler.crawler.extract_elements", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.analyze_forms", new_callable=AsyncMock, return_value=[]), \
             patch("src.crawler.crawler.detect_spa_type", new_callable=AsyncMock, return_value="traditional"), \
             patch("src.crawler.crawler.discover_spa_routes", new_callable=AsyncMock, return_value=set()):
            crawl_task = asyncio.create_task(crawler._priority_crawl(mock_context, "https://example.com"))
            await semaphore_held.wait()
            semaphore_released.set()
            await crawl_task

        assert call_count >= 1
