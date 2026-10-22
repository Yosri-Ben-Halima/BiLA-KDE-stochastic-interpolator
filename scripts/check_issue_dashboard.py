"""Rendered checks: uv run --with playwright python -m scripts.check_issue_dashboard."""

import argparse
import json
import shutil
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from scripts.issue_dashboard import make_server

ROOT = Path(__file__).resolve().parents[1]


def fixture_issue(
    root,
    epic,
    name,
    title,
    status="open",
    owner="unassigned",
    blockers="none",
    body="Test question.",
):
    folder = root / ".scratch" / epic
    (folder / "issues").mkdir(parents=True, exist_ok=True)
    (folder / "map.md").write_text(f"# {epic.title()}\n\nStatus: open\n")
    path = folder / "issues" / f"{name}.md"
    path.write_text(
        f"# {title}\n\nParent: [{epic}](../map.md)\nType: task\n"
        f"Mode: AFK\nStatus: {status}\nAssignee: {owner}\nBlocked by: {blockers}\n"
        f"\n## Question\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Page-wide overflow"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Also capture the real running dashboard")
    parser.add_argument("--output", type=Path, default=ROOT / ".scratch/issue-dashboard/evidence")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []
    errors = []
    expected_network_failure = False
    chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.exists():
        raise FileNotFoundError("Installed Chrome is required for this local verification command")
    with tempfile.TemporaryDirectory(prefix="bila-dashboard-check-") as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
        shutil.copytree(ROOT / "dashboard", root / "dashboard")
        fixture_issue(root, "implementation", "01-input", "Input contracts", status="resolved")
        fixture_issue(
            root, "implementation", "02-package", "Package and examples", status="resolved"
        )
        campaign = fixture_issue(
            root, "research", "01-campaign", "Complete campaign", owner="Codex"
        )
        repair = fixture_issue(root, "research", "02-repair", "Repair density", blockers="01")
        fixture_issue(root, "research", "03-verdict", "Write verdict", blockers="02")
        unsafe_title = "Inspect <script>window.UNSAFE=1</script>"
        fixture_issue(
            root,
            "dashboard",
            "01-inspect",
            unsafe_title,
            body=(
                '<img src=x onerror="window.UNSAFE=1">\n\n[Unsafe](javascript:alert(1))\n'
                "\n[Malformed](%E0%A4%A)\n"
            ),
        )
        summary_path = root / '.scratch/implementation/summary.md'
        summary_path.write_text(
            '# Results\n\n## Executive summary\n\nDelivered prototype.\n\n'
            '## Conclusion\n\n[Evidence](map.md).\n', encoding='utf-8'
        )
        for name, status in [('history-original', 'running'), ('history-recovered', 'interrupted'), ('history-validation', 'validated')]:
            folder = root / 'results' / name
            folder.mkdir(parents=True)
            (folder / 'manifest.json').write_text(json.dumps({'stage':'history_fixture','status':status,'planned':3,'attempted':2,'source_signature':'frozen-history-source','budget_seconds':60,'elapsed_seconds':20}))
            (folder / 'results.json').write_text(json.dumps({'results':[{'status':'success'},{'status':'time_limit'},{'status':'untested'}]}))
        (root / 'results/campaign-history.json').write_text(json.dumps({'campaigns':[{'id':'original','title':'Recovered campaign','date':'2026-10-21','source':'results/history-recovered','original_source':'results/history-original','stages':[{'source':'results/history-validation','role':'validation','label':'Linked smoke'}]}]}))
        server = make_server(root, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=str(chrome), headless=True)
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1050}, device_scale_factor=1
                )
                page.set_default_timeout(5000)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "console",
                    lambda message: (
                        errors.append(f"Console: {message.text}")
                        if message.type == "error" and not expected_network_failure
                        else None
                    ),
                )
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#view-count")).to_have_text("6")
                assert page.locator(".epic-card").count() == 3
                epic_card = page.locator('.epic-card').filter(
                    has=page.get_by_role('button', name='Filter epic: Implementation', exact=True)
                )
                results_button = epic_card.get_by_role('button', name='Results & conclusions')
                results_button.click()
                epic_summary = page.locator('#epic-results-dialog')
                expect(epic_summary).to_be_visible()
                expect(epic_summary).to_contain_text('Delivered prototype.')
                expect(page.locator('#epic-results-title')).to_have_text('Implementation')
                assert page.evaluate("document.querySelector('#epic-results-dialog').matches(':modal')")
                assert 'blur(' in page.evaluate("getComputedStyle(document.querySelector('#epic-results-dialog'), '::backdrop').backdropFilter")
                expect(page.locator('#view-count')).to_have_text('6')
                page.locator('#epic-results-close').focus()
                summary_path.write_text(
                    '# Results\n\n## Executive summary\n\nUpdated findings.\n',
                    encoding='utf-8',
                )
                expect(epic_summary).to_contain_text('Updated findings.', timeout=15000)
                expect(page.locator('#epic-results-close')).to_be_focused()
                page.keyboard.press('Escape')
                expect(epic_summary).not_to_be_visible()
                expect(results_button).to_be_focused()
                results_button.click()
                page.mouse.click(5, 5)
                expect(epic_summary).not_to_be_visible()
                results_button.click()
                page.locator('#epic-results-close').click()
                expect(results_button).to_be_focused()
                page.get_by_role('button', name='Filter epic: Implementation', exact=True).click()
                expect(page.locator('#view-count')).to_have_text('2')
                page.get_by_role('button', name='Filter epic: Implementation', exact=True).click()
                expect(page.locator('#view-count')).to_have_text('6')
                page.set_viewport_size({'width':390,'height':844})
                results_button.click()
                no_overflow(page)
                expect(epic_summary).to_be_visible()
                page.screenshot(path=str(args.output / 'epic-modal-mobile.png'))
                page.locator('#epic-results-close').click()
                page.set_viewport_size({'width':1440,'height':1050})
                checks.append('epic results modal: blurred backdrop, live refresh, focus, Escape/backdrop/button dismissal and mobile')
                expect(page.locator("#campaign")).to_be_hidden()
                no_overflow(page)
                page.screenshot(path=str(args.output / "desktop-fixture.png"), full_page=True)
                checks.append("Desktop rendering, source counts and unavailable campaign")
                page.locator('#campaign-history-open').click()
                history = page.locator('#campaign-history-dialog')
                expect(history).to_be_visible()
                expect(page.locator('.history-record')).to_have_count(1)
                expect(history).to_contain_text('Recovered accounting is attached to the original run')
                expect(history).to_contain_text('Linked smoke')
                expect(history).to_contain_text('frozen-history-source')
                expect(history).to_contain_text('1 success')
                expect(history).to_contain_text('Purpose not recorded in the original manifest')
                history.get_by_role('button', name='Inspect stage: Linked smoke').click()
                expect(page.locator('#campaign-history-body')).to_contain_text('1 untested')
                expect(page.locator('#campaign-history-body')).to_contain_text('Saved research narrative')
                history.get_by_role('button', name='← Back to campaign').click()
                expect(history).to_contain_text('Recovered accounting is attached to the original run')
                assert page.evaluate("document.querySelector('#campaign-history-dialog').matches(':modal')")
                page.screenshot(path=str(args.output / 'history-desktop.png'))
                page.set_viewport_size({'width':390,'height':844})
                no_overflow(page)
                page.screenshot(path=str(args.output / 'history-mobile.png'))
                page.keyboard.press('Escape')
                expect(history).not_to_be_visible()
                expect(page.locator('#campaign-history-open')).to_be_focused()
                expect(page.locator('#view-count')).to_have_text('6')
                page.set_viewport_size({'width':1440,'height':1050})
                checks.append('Campaign history groups recovery and validation, shows outcomes/provenance, and preserves the active view on close')

                page.route('**/api/history', lambda route: route.fulfill(
                    status=200, content_type='application/json',
                    body=json.dumps({'campaigns': [], 'warnings': []}),
                ))
                page.locator('#campaign-history-open').click()
                expect(history).to_contain_text('No saved campaigns were found')
                expect(page.locator('.history-record')).to_have_count(0)
                page.keyboard.press('Escape')
                page.unroute('**/api/history')
                expected_network_failure = True
                page.route('**/api/history', lambda route: route.fulfill(status=503))
                page.locator('#campaign-history-open').click()
                expect(page.locator('#campaign-history-note')).to_contain_text('History unavailable')
                page.keyboard.press('Escape')
                page.unroute('**/api/history')
                page.locator('#campaign-history-open').click()
                expect(page.locator('.history-record')).to_have_count(1)
                expect(page.locator('#campaign-history-note')).not_to_contain_text('History unavailable')
                expect(history).to_contain_text('Recovered accounting is attached to the original run')
                page.keyboard.press('Escape')
                expected_network_failure = False
                checks.append('Empty campaign history and failed fetch recover correctly when the window is reopened')

                page.set_viewport_size({"width": 390, "height": 844})
                expect(page.locator("#list-view")).to_have_attribute("aria-pressed", "true")
                no_overflow(page)
                page.screenshot(path=str(args.output / "mobile-fixture.png"), full_page=True)
                checks.append("390px layout without page-wide overflow")
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.locator("#status-filter").select_option("ready")
                expect(page.locator("#view-count")).to_have_text("1")
                page.locator(".task-card").click()
                expect(page.locator("#detail")).to_be_visible()
                expect(page.locator("#detail-title")).to_have_text(unsafe_title)
                assert page.evaluate("window.UNSAFE === undefined")
                assert page.locator('#detail-body a[href^="javascript:"]').count() == 0
                checks.append("Inert HTML/executable links and malformed-link rendering")
                page.keyboard.press("Escape")
                page.locator("#status-filter").select_option("")
                page.locator("#epic-filter").select_option(".scratch/research/map.md")
                page.locator("#search").fill("Repair")
                expect(page.locator("#view-count")).to_have_text("1")
                page.locator(".task-card").click()
                expect(page.locator("#detail-title")).to_have_text("Repair density")
                page.get_by_role("button", name="Complete campaign", exact=True).click()
                expect(page.locator("#detail-title")).to_have_text("Complete campaign")
                page.locator("#detail-back").click()
                expect(page.locator("#detail-title")).to_have_text("Repair density")
                page.keyboard.press("Escape")
                checks.append("Intersecting filters, dependency navigation and Escape")
                page.locator("#list-view").click()
                page.locator(".issue-link").click()
                campaign.write_text(
                    campaign.read_text().replace("Status: open", "Status: resolved")
                )
                expect(page.locator("#detail-status")).to_have_text("Ready", timeout=12000)
                expect(page.locator("#search")).to_have_value("Repair")
                expect(page.locator("#epic-filter")).to_have_value(".scratch/research/map.md")
                expect(page.locator("#list-view")).to_have_attribute("aria-pressed", "true")
                checks.append("Automatic Markdown refresh preserves filters, view and open issue")
                page.keyboard.press("Escape")
                expect(page.locator(".issue-link")).to_be_focused()
                checks.append("Focus restores to the visible list trigger")
                page.locator("#search").fill("no-such-issue")
                expect(page.locator("#empty")).to_be_visible()
                page.locator("#empty-reset").click()
                expect(page.locator("#view-count")).to_have_text("6")
                page.locator("#status-filter").select_option("resolved")
                expect(page.locator("#view-count")).to_have_text("3")
                checks.append("Empty state, reset and completed history")
                expected_network_failure = True
                page.route("**/api/state", lambda route: route.abort())
                page.locator("#refresh").click()
                expect(page.locator("#notice")).to_contain_text(
                    "Showing the last successful snapshot"
                )
                expect(page.locator("#view-count")).to_have_text("3")
                page.unroute("**/api/state")
                page.locator("#refresh").click()
                expect(page.locator("#freshness")).to_have_text("Live from Markdown")
                expected_network_failure = False
                checks.append("Disconnected snapshot warning and successful recovery")
                page.locator("#status-filter").select_option("")
                page.locator("#dependency-view").click()
                page.locator("#search").fill("Write verdict")
                expect(page.locator("#dependency-view")).to_have_attribute("aria-pressed", "true")
                expect(page.locator(".graph-node")).to_have_count(3)
                expect(page.locator(".graph-node.context")).to_have_count(2)
                expect(page.locator(".graph-edge")).to_have_count(2)
                expect(page.locator("#board")).to_be_hidden()
                expect(page.locator("#list")).to_be_hidden()
                graph_task = page.locator(
                    '.graph-node[data-issue=".scratch/research/issues/03-verdict.md"]'
                )
                graph_task.focus()
                page.keyboard.press("Enter")
                expect(page.locator("#detail-title")).to_have_text("Write verdict")
                page.keyboard.press("Escape")
                expect(graph_task).to_be_focused()
                page.locator("#graph-zoom-out").click()
                expect(page.locator("#graph-scale")).to_have_text("80%")
                campaign.write_text(
                    campaign.read_text().replace("Complete campaign", "Campaign finished")
                )
                expect(page.locator("#dependency")).to_contain_text(
                    "Campaign finished", timeout=12000
                )
                expect(page.locator("#dependency-view")).to_have_attribute("aria-pressed", "true")
                expect(page.locator("#graph-scale")).to_have_text("80%")
                page.set_viewport_size({"width": 390, "height": 844})
                expect(page.locator("#dependency-view")).to_have_attribute("aria-pressed", "true")
                no_overflow(page)
                page.screenshot(path=str(args.output / "dependency-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1050})
                checks.append(
                    "Dependency graph retains prerequisites, opens details by keyboard, preserves zoom/view on refresh and resize"
                )
                page.locator("#list-view").click()
                page.locator("#search").fill("Repair")
                page.locator(".issue-link").click()
                repair.unlink()
                expect(page.locator("#detail")).to_be_hidden(timeout=12000)
                expect(page.locator("#view-count")).to_have_text("0")
                expect(page.locator("#empty")).to_be_visible()
                checks.append("Deleted selected issue closes obsolete details after refresh")
                run = root / "results/research"
                run.mkdir(parents=True)
                (run / "manifest.json").write_text(
                    json.dumps(
                        {
                            "stage": "research",
                            "status": "running",
                            "planned": 50,
                            "budget_seconds": 14400,
                        }
                    )
                )
                (run / "progress.json").write_text(
                    json.dumps(
                        {
                            "attempted": 5,
                            "elapsed_seconds": 1200,
                            "last_case": "case-1",
                            "last_method": "bila",
                            "last_status": "success",
                        }
                    )
                )
                entries = [
                    {
                        "id": "start",
                        "at": "20261021T100000Z",
                        "title": "Compare models",
                        "detail": '<img src=x onerror="window.UNSAFE=1">',
                        "next": "Audit results",
                        "testing": "Can the full reconstruction finish?",
                        "why": "Separate computation from interval precision.",
                        "observed": "A recorded outcome, not a forecast.",
                        "meaning": "<script>window.UNSAFE=1</script>",
                    }
                ]
                activity = run / "activity.json"
                activity.write_text(json.dumps({"entries": entries}))
                page.locator("#refresh").click()
                timeline = page.locator(".campaign-thread")
                expect(timeline).to_have_attribute("open", "")
                expect(timeline).to_contain_text("Compare models")
                expect(timeline.locator(".thread-narrative")).to_contain_text("Meaning so far")
                expect(timeline.locator(".thread-narrative")).to_contain_text("Separate computation from interval precision.")
                expect(timeline.locator("time")).not_to_contain_text("Invalid Date")
                assert page.locator(".campaign-thread img").count() == 0
                assert page.evaluate("window.UNSAFE === undefined")
                summary = timeline.locator("summary")
                summary.click()
                expect(timeline).not_to_have_attribute("open", "")
                entries.append(
                    {
                        "id": "audit",
                        "at": "2026-10-21T11:00:00Z",
                        "title": "Outputs checked",
                        "detail": "Endpoint audit passed. " * 80,
                    }
                )
                activity.write_text(json.dumps({"entries": entries}))
                expect(timeline).to_contain_text("Outputs checked", timeout=12000)
                expect(timeline).not_to_have_attribute("open", "")
                expect(page.locator(".campaign-heading")).to_be_visible()
                page.locator("#refresh").click()
                expect(timeline).not_to_have_attribute("open", "")
                summary.focus()
                page.keyboard.press("Enter")
                expect(timeline).to_have_attribute("open", "")
                expect(summary).to_be_focused()
                scroll_setup = page.locator(".thread-timeline").evaluate(
                    "(node) => { node.scrollTop = 80; return {top:node.scrollTop, height:node.clientHeight, content:node.scrollHeight, open:node.closest('details').open}; }"
                )
                (args.output / "scroll-setup.json").write_text(json.dumps(scroll_setup))
                assert scroll_setup["top"] == 80, scroll_setup
                with page.expect_response("**/api/state"):
                    page.locator("#refresh").click()
                expect(timeline).to_have_attribute("open", "")
                expect(page.locator(".thread-timeline")).to_have_js_property("scrollTop", 80)
                page.set_viewport_size({"width": 390, "height": 844})
                no_overflow(page)
                page.screenshot(
                    path=str(args.output / "campaign-thread-mobile.png"), full_page=True
                )
                page.set_viewport_size({"width": 1440, "height": 1050})
                checks.append(
                    "Campaign thread defaults open, refreshes inert text, retains collapse and supports keyboard/mobile"
                )
                (run / "progress.json").write_text(
                    json.dumps(
                        {
                            "last_case": "unreached-case",
                            "last_method": "bila",
                            "last_status": "untested",
                        }
                    )
                )
                page.locator("#refresh").click()
                expect(page.locator(".thread-latest")).to_contain_text(
                    "Not attempted within the campaign budget"
                )
                expect(page.locator(".thread-latest")).not_to_contain_text("last completed result")
                (run / "manifest.json").write_text(
                    json.dumps(
                        {
                            "stage": "research",
                            "status": "interrupted",
                            "attempted": 5,
                            "planned": 50,
                            "elapsed_seconds": 1200,
                            "budget_seconds": 14400,
                        }
                    )
                )
                page.locator("#refresh").click()
                expect(page.locator(".live-tag")).to_have_text("Interrupted")
                assert not errors, errors
                if args.url:
                    page.goto(args.url)
                    expect(page.locator("#freshness")).to_have_text("Live from Markdown")
                    no_overflow(page)
                    page.screenshot(path=str(args.output / "desktop-real.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    no_overflow(page)
                    page.screenshot(path=str(args.output / "mobile-real.png"), full_page=True)
                    page.set_viewport_size({"width": 1440, "height": 1050})
                    if (
                        page.locator(".campaign-thread").count()
                        and page.locator(".campaign-thread").get_attribute("open") is not None
                    ):
                        page.locator(".campaign-thread summary").click()
                    page.locator("#dependency-view").click()
                    page.locator("#epic-filter").select_option(
                        ".scratch/bila-kde-validation/map.md"
                    )
                    page.locator("#graph-fit").click()
                    no_overflow(page)
                    page.screenshot(
                        path=str(args.output / "dependency-real-desktop.png"), full_page=True
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    no_overflow(page)
                    page.screenshot(
                        path=str(args.output / "dependency-real-mobile.png"), full_page=True
                    )
                    checks.append("Real workspace desktop/mobile screenshots")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            (args.output / "browser-check.json").write_text(
                json.dumps({"checks": checks, "page_errors": errors}, indent=2)
            )
    print(json.dumps({"passed": len(checks), "checks": checks, "page_errors": errors}, indent=2))


if __name__ == "__main__":
    main()
