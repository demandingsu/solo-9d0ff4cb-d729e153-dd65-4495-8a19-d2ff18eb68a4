import httpx
import pytest

from app.scraper import (
    inspect_issue,
    normalize_edition,
    normalize_issue,
    parse_page_numbers,
    split_ownership,
)
from sample_site.main import app as sample_app


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=sample_app),
        base_url="http://sample.test",
        follow_redirects=True,
    )


@pytest.mark.asyncio
async def test_clean_issue_is_qualified_and_crawls_pagination():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/clean/page/1.html", client=client
        )

    assert report.status == "合格"
    assert report.issue_no == "2024-05-01"
    assert report.edition == "第3版"
    assert report.total_pages == 6
    assert len(report.directory_pages) == 2
    assert [page.status for page in report.pages] == ["covered"] * 6
    assert len(report.accepted_scans) == 5
    assert report.failures == []
    assert report.ignored_scans == []
    # page 2 and 3 come from the same spread scan
    assert report.pages[1].sources[0].code == report.pages[2].sources[0].code
    assert report.pages[1].sources[0].pages_text == "2-3"


@pytest.mark.asyncio
async def test_legacy_and_new_links_that_land_on_same_detail_count_once():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/redirect/page/1.html", client=client
        )

    # Old and new links appear in different directory pages but resolve to
    # the same detail; they must merge into one scan instead of a rescan.
    assert report.status == "合格"
    assert all(page.status == "covered" for page in report.pages)
    assert report.conflict_pages == []
    assert len(report.accepted_scans) == 5
    assert report.entry_count == 7
    assert report.detail_count == 5

    first = report.pages[0].sources[0]
    assert first.is_merged
    assert sorted(first.entry_urls) == [
        "http://sample.test/scan/redirect/d1-old.html",
        "http://sample.test/scan/redirect/d1.html",
    ]
    assert first.detail_url == "http://sample.test/scan/redirect/d1.html"
    assert any("2 个入口" in note for note in first.notes)

    spread = report.pages[1].sources[0]
    assert spread.detail_url == "http://sample.test/scan/redirect/d2.html"
    assert len(spread.entry_urls) == 2


@pytest.mark.asyncio
async def test_legacy_alias_does_not_mask_a_real_rescan():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/conflict/page/1.html", client=client
        )

    # b2 (page 2-3) and b3 (page 3) are genuinely different details.  The
    # extra legacy entry b3-old points at b3 and must not create a third scan,
    # but page 3 must still be a conflict.
    assert report.status == "不合格"
    assert report.conflict_pages == [3]
    b3 = [scan for scan in report.accepted_scans if scan.detail_url.endswith("/b3.html")]
    assert len(b3) == 1
    assert sorted(b3[0].entry_urls) == [
        "http://sample.test/scan/conflict/b3-old.html",
        "http://sample.test/scan/conflict/b3.html",
    ]
    assert len(report.pages[2].sources) == 2


@pytest.mark.asyncio
async def test_one_failed_entry_forces_verification_even_if_alias_ok():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/alias-failure/page/1.html", client=client
        )

    # Page 2 is fully covered by the working new entry, but the failed legacy
    # entry for the same record must still make the issue "needs verification".
    assert report.status == "待核实"
    assert report.status != "合格"
    assert [page.status for page in report.pages] == ["covered"] * 4
    assert report.missing_pages == []
    assert report.conflict_pages == []
    assert len(report.accepted_scans) == 4
    assert len(report.failures) == 1
    failure = report.failures[0]
    assert failure.stage == "详情"
    assert "HTTP 404" in failure.message
    assert failure.url == "http://sample.test/scan/alias-failure/f2-lost.html"
    # The working entry still contributes its entry and landing address to the
    # page grid, while the failed entry remains visible in the failure list.
    f2 = [scan for scan in report.accepted_scans if scan.detail_url.endswith("/f2.html")]
    assert len(f2) == 1
    assert "http://sample.test/scan/alias-failure/f2.html" in f2[0].entry_urls


@pytest.mark.asyncio
async def test_conflict_and_missing_pages_make_issue_unqualified():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/conflict/page/1.html", client=client
        )

    assert report.status == "不合格"
    assert report.conflict_pages == [3]
    assert report.missing_pages == [4, 5]
    assert len(report.pages[2].sources) == 2
    assert len(report.ignored_scans) == 2
    reasons = " ".join(scan.reason for scan in report.ignored_scans)
    assert "期版不一致" in reasons
    assert "缺少图片链接" in reasons
    assert len(report.directory_pages) == 3
    assert report.failures == []


@pytest.mark.asyncio
async def test_failed_detail_forces_verification_status():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/pending/page/1.html", client=client
        )

    assert report.status == "待核实"
    assert len(report.failures) == 1
    assert report.failures[0].stage == "详情"
    assert "HTTP 404" in report.failures[0].message
    assert report.conflict_pages == [4]
    assert report.missing_pages == [5, 9, 11, 12]
    assert len(report.directory_pages) == 3
    assert len(report.ignored_scans) == 1
    assert "期版不一致" in report.ignored_scans[0].reason


@pytest.mark.asyncio
async def test_detail_failure_is_not_hidden_even_if_pages_are_covered():
    async with make_client() as client:
        report = await inspect_issue(
            "http://sample.test/issues/pending/page/1.html", client=client
        )

    # The visible page grid still reports findings, but the overall verdict is
    # never "合格" while a detail fetch failed.
    assert report.status != "合格"
    assert report.status_key == "pending"


def test_page_number_parsing_handles_spreads_and_lists():
    assert parse_page_numbers("5") == [5]
    assert parse_page_numbers("第2—3版") == [2, 3]
    assert parse_page_numbers("2,3,5-7") == [2, 3, 5, 6, 7]
    assert parse_page_numbers("12、13") == [12, 13]
    assert parse_page_numbers("13-12") == [12, 13]
    assert parse_page_numbers("") == []


def test_ownership_and_tokens_are_normalised():
    assert split_ownership("2024-05-01 第3版") == ("2024-05-01", "第3版")
    assert split_ownership("期号：2024-05-01　版次：第3版") == ("2024-05-01", "第3版")
    assert normalize_issue("2024年5月1日") == "2024-05-01"
    assert normalize_issue("2024-05-01") == "2024-05-01"
    assert normalize_edition("第三版") == "3"
    assert normalize_edition("第3版") == "3"
    assert normalize_edition("3版") == "3"
    assert normalize_edition("第4版") != normalize_edition("第3版")
