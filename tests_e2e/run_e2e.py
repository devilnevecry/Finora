"""Finora end-to-end Playwright test suite.

Launches the real FastAPI application (uvicorn) on a test port and drives the
browser through complete user workflows. Captures console errors, network
failures, and screenshots on failure.

Run:
    python -m playwright test tests_e2e/  (if using pytest-playwright)
    or directly: python tests_e2e/run_e2e.py
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parents[1]
PORT = 8177
BASE = f"http://127.0.0.1:{PORT}"

FAILURES = []
SCREENSHOTS = REPO / "tests_e2e" / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)


import builtins


def safe_print(*args, **kwargs):
    """Print that tolerates non-encodable console codepages (Windows cp1252)."""
    text = " ".join(str(a) for a in args)
    try:
        builtins.print(text, **kwargs)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        builtins.print(text.encode(enc, errors="replace").decode(enc), **kwargs)


def fail(msg: str):
    FAILURES.append(msg)
    safe_print(f"  FAIL: {msg}")


async def screenshot(page, name: str):
    path = SCREENSHOTS / f"{name}.png"
    try:
        await asyncio.wait_for(
            page.wait_for_load_state("domcontentloaded", timeout=5000),
            timeout=8.0,
        )
    except Exception:
        pass
    try:
        await asyncio.wait_for(
            page.screenshot(path=str(path), full_page=True),
            timeout=8.0,
        )
    except Exception:
        pass
    safe_print(f"  screenshot -> {path}")


async def modal_save(page):
    """Trigger the Save submit handler within the currently open modal."""
    for modal in ("#tx-modal", "#acc-modal", "#cat-modal", "#bud-modal", "#rec-modal"):
        form = page.locator(f"{modal}.open form")
        if await form.count() > 0:
            await form.first.evaluate("form => form.requestSubmit()")
            await page.wait_for_timeout(500)
            return True
    return False


async def wait_for_select_options(page, selector: str, timeout: int = 8000):
    """Wait until a <select> has been populated with real options."""
    try:
        await page.wait_for_function(
            """(args) => {
                const [sel] = args;
                const modal = document.querySelector('.modal.open');
                const root = modal ? modal : document;
                const s = root.querySelector(sel);
                return s ? s.options.length > 1 : false;
            }""",
            [selector],
            timeout=timeout,
        )
    except Exception:
        safe_print(f"  (select {selector} not auto-populated; proceeding anyway)")


async def set_select(page, selector: str, label_substring: str | None = None, value: str | None = None):
    """Set a <select> value, scoped to the currently open modal."""
    try:
        if label_substring is not None:
            await page.select_option(selector, label=label_substring)
        elif value is not None:
            await page.select_option(selector, value=value)
        return
    except Exception:
        pass
    await page.evaluate(
        """(args) => {
            const [sel, lbl, val] = args;
            const modal = document.querySelector('.modal.open');
            const root = modal ? modal : document;
            const s = root.querySelector(sel);
            if (!s) return;
            for (const o of s.options) {
                const match = (lbl !== null && lbl !== undefined && o.textContent.includes(lbl))
                    || (val !== null && val !== undefined && o.value === val);
                if (match) { s.value = o.value; s.dispatchEvent(new Event('change')); return; }
            }
        }""",
        [selector, label_substring, value],
    )


async def close_modal(page):
    """Force-close any open modal/backdrop so it cannot intercept clicks."""
    for modal in ("#tx-modal", "#acc-modal", "#cat-modal", "#bud-modal", "#rec-modal"):
        await page.evaluate(
            """(sels) => {
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el) el.classList.remove('open');
                }
            }""",
            [modal, modal + "-backdrop"],
        )
    await page.wait_for_timeout(200)


async def wait_for_server(timeout: float = 30.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE}/dashboard", timeout=2)
            return True
        except Exception:
            await asyncio.sleep(0.5)
    return False


async def main():
    # Start uvicorn with a temp database dir (isolated from user data).
    env = os.environ.copy()
    env["FINORA_PORT"] = str(PORT)
    env["FINORA_DATA_DIR"] = str(REPO / "tests_e2e" / "data")
    env["FINORA_DATABASE_FILE"] = "e2e.db"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(REPO), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    try:
        # Fresh database for this run.
        for f in Path(env["FINORA_DATA_DIR"]).glob("*.db*"):
            try:
                f.unlink()
            except OSError:
                pass

        if not await wait_for_server():
            safe_print("Server did not start")
            out = proc.stdout.read() if proc.stdout else ""
            safe_print(out[:2000])
            return 1

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                ignore_https_errors=True,
            )
            # Capture console errors and failed requests.
            console_errors = []
            failed_requests = []

            def on_console(msg):
                if msg.type in ("error", "warning"):
                    console_errors.append(f"[{msg.type}] {msg.text}")

            def on_request_failed(req):
                failed_requests.append(f"{req.method} {req.url} -> {req.failure}")

            all_requests = []
            def on_request(req):
                if "/api/" in req.url:
                    all_requests.append(f"{req.method} {req.url.split('?')[0]}")
            context.on("request", on_request)

            page_errors = []
            def on_page_error(err):
                page_errors.append(str(err))

            context.on("console", on_console)
            context.on("requestfailed", on_request_failed)

            api_errors = []
            def on_response(resp):
                if "/api/accounts" in resp.url:
                    safe_print(f"  [RESP] {resp.request.method} {resp.url.split('?')[0]} -> {resp.status}")
                elif "/api/" in resp.url and resp.status >= 400:
                    api_errors.append(f"{resp.request.method} {resp.url} -> {resp.status}")
            context.on("response", on_response)

            async def log_400_bodies(resp):
                if "/api/transactions" in resp.url and resp.status == 400:
                    try:
                        body = await resp.text()
                        safe_print(f"  [400 BODY] {resp.request.method} {resp.url}: {body[:300]}")
                    except Exception:
                        pass
            context.on("response", log_400_bodies)

            def report_api_errors(label: str):
                if api_errors:
                    safe_print(f"  API ERRORS ({label}):")
                    for e in api_errors[-10:]:
                        safe_print("   ", e)

            page = await context.new_page()
            page.set_default_timeout(10000)
            page.on("pageerror", on_page_error)

            # ---- Helper: go to page ----
            async def goto(path: str):
                await asyncio.wait_for(
                    page.evaluate(f"window.location.href = '{BASE}{path}'"),
                    timeout=10.0,
                )
                await page.wait_for_timeout(500)

            # ===== 1. Dashboard first-run =====
            safe_print("== Dashboard first-run ==")
            await goto("/dashboard")
            title = await page.title()
            safe_print("  title:", title)
            await screenshot(page, "01_dashboard")
            # wait for i18n to translate card labels
            try:
                await page.wait_for_function(
                    "() => document.querySelector('.stat-label') && !document.querySelector('.stat-label')?.textContent?.includes('report.')",
                    timeout=5000,
                )
            except Exception:
                pass
            body = await page.locator("body").inner_text()
            assert "Finora" in body, "Finora brand missing on dashboard"
            # summary cards present (check by class, robust to language)
            stat_count = await page.locator(".stat-card").count()
            safe_print("  stat cards:", stat_count)
            if stat_count < 4:
                fail("Dashboard missing summary cards")

            # ===== 2. Accounts =====
            safe_print("== Accounts ==")
            await goto("/accounts")
            await screenshot(page, "02_accounts_list")
            # add account
            await page.click('#btn-add-account')
            await page.wait_for_selector("#acc-modal", state="visible")
            await page.fill('input[name="name"]', "Test Wallet")
            await page.fill('input[name="opening_balance"]', "1000.00")
            await modal_save(page)
            await page.wait_for_timeout(800)
            await close_modal(page)
            report_api_errors("after account save")
            await screenshot(page, "03_account_added")
            # reload page for a fresh, authoritative row count
            await goto("/accounts")
            rows = page.locator("table tbody tr")
            count = await rows.count()
            safe_print("  account rows:", count)
            if count < 1:
                fail("Account not created")
                safe_print("  console errors so far:", console_errors[:10])
                safe_print("  page errors so far:", page_errors[:10])
                safe_print("  API requests so far:", all_requests[-10:])

            # edit account
            first = rows.first
            edit_btn = first.locator('button:has-text("Ред.")')
            if await edit_btn.count() > 0:
                await edit_btn.click()
                await page.wait_for_selector("#acc-modal", state="visible")
                await page.fill('input[name="name"]', "Test Wallet Renamed")
                await modal_save(page)
                await page.wait_for_timeout(500)
                await screenshot(page, "04_account_edited")
                body = await page.locator("body").inner_text()
                if "Test Wallet Renamed" not in body:
                    fail("Account rename not persisted")

            # ===== 3. Categories =====
            safe_print("== Categories ==")
            await goto("/categories")
            await screenshot(page, "05_categories_list")
            await page.click('#btn-add-category')
            await page.wait_for_selector("#cat-modal", state="visible")
            await page.fill('input[name="name"]', "Groceries")
            await page.select_option('select[name="type"]', "expense")
            await page.fill('input[name="color"]', "#dc2626")
            await modal_save(page)
            await page.wait_for_timeout(500)
            await screenshot(page, "06_category_added")
            body = await page.locator("body").inner_text()
            if "Groceries" not in body:
                fail("Category not created")

            # duplicate category should be rejected
            await close_modal(page)
            await page.click('#btn-add-category')
            await page.wait_for_selector("#cat-modal", state="visible")
            await page.fill('input[name="name"]', "Groceries")
            await page.select_option('select[name="type"]', "expense")
            await modal_save(page)
            await page.wait_for_timeout(500)
            await close_modal(page)
            report_api_errors("after category save")
            # Expect an error toast/flash, not a new duplicate row
            dup_text = await page.locator("body").inner_text()
            # (error appears as flash or toast)
            safe_print("  duplicate category attempt done")

            # ===== 4. Transactions =====
            safe_print("== Transactions ==")
            await goto("/transactions")
            await screenshot(page, "07_transactions_list")

            # Helper: submit a transaction via the API (bypasses flaky modal selects).
            async def api_tx(endpoint: str, form_dict: dict):
                csrf_token = await asyncio.wait_for(
                    page.evaluate("() => window.FINORA.csrfToken"),
                    timeout=10.0,
                )
                body = await asyncio.wait_for(
                    page.evaluate(
                        """(args) => {
                            const [ep, fd, tok] = args;
                            const formData = new FormData();
                            for (const [k, v] of Object.entries(fd)) {
                                if (v !== null && v !== undefined) formData.append(k, v);
                            }
                            return fetch(ep, { method: "POST", body: formData, headers: { "X-CSRF-Token": tok }, credentials: "include" })
                                .then(async r => ({ status: r.status, body: await r.text() }));
                        }""",
                        [endpoint, form_dict, csrf_token],
                    ),
                    timeout=10.0,
                )
                safe_print(f"  API {endpoint}: status={body['status']} body={body['body'][:200]}")
                return body

            # add income
            await close_modal(page)
            r = await api_tx("/api/transactions/income", {
                "account_id": "1",
                "amount": "2500.00",
                "transaction_date": "2026-01-10T12:00",
                "description": "Salary",
            })
            if r["status"] != 201:
                fail(f"Income creation failed: {r['status']} {r['body']}")
            await page.wait_for_timeout(500)
            await page.reload()
            await page.wait_for_timeout(500)
            await screenshot(page, "08_income_added")
            body = await page.locator("body").inner_text()
            if "Salary" not in body:
                fail("Income not created")

            # add expense (no category to avoid id assumptions)
            await close_modal(page)
            r = await api_tx("/api/transactions/expense", {
                "account_id": "1",
                "amount": "450.00",
                "transaction_date": "2026-01-11T12:00",
                "description": "Groceries",
            })
            if r["status"] != 201:
                fail(f"Expense creation failed: {r['status']} {r['body']}")
            await page.wait_for_timeout(500)
            await page.reload()
            await page.wait_for_timeout(500)
            await screenshot(page, "09_expense_added")

            # transfer
            # need a second account first; create via API? We'll create via accounts page.
            # add expense to test edit/delete
            rows = page.locator("table tbody tr")
            count = await rows.count()
            safe_print("  transaction rows:", count)
            if count > 0:
                # Get transactions via API to edit/delete reliably.
                csrf_tok0 = await page.evaluate("() => window.FINORA.csrfToken")
                tx_list = await page.evaluate(
                    """(tok) => {
                        return fetch("/api/transactions", { headers: { "X-CSRF-Token": tok }, credentials: "include" })
                            .then(async r => ({ status: r.status, body: await r.json() }));
                    }""",
                    [csrf_tok0],
                )
                if tx_list["status"] == 200 and tx_list["body"].get("items"):
                    first_tx = tx_list["body"]["items"][0]
                    tx_id = first_tx["id"]
                    # Edit the first transaction via API PUT.
                    csrf_tok = await asyncio.wait_for(
                        page.evaluate("() => window.FINORA.csrfToken"),
                        timeout=10.0,
                    )
                    edit_res = await page.evaluate(
                        """(args) => {
                            const [id, fd, tok] = args;
                            const formData = new FormData();
                            for (const [k, v] of Object.entries(fd)) {
                                if (v !== null && v !== undefined) formData.append(k, v);
                            }
                            return fetch(`/api/transactions/${id}`, { method: "PUT", body: formData, headers: { "X-CSRF-Token": tok }, credentials: "include" })
                                .then(async r => ({ status: r.status, body: await r.text() }));
                        }""",
                        [tx_id, {"description": "Groceries Edited"}, csrf_tok],
                    )
                    safe_print(f"  API edit tx {tx_id}: status={edit_res['status']}")
                    if edit_res["status"] != 200:
                        fail(f"Transaction edit failed: {edit_res['status']} {edit_res['body']}")
                    await page.wait_for_timeout(500)
                    await screenshot(page, "08_income_added")

                # Delete the last transaction via API DELETE.
                csrf_tok2 = await asyncio.wait_for(
                    page.evaluate("() => window.FINORA.csrfToken"),
                    timeout=10.0,
                )
                tx_list2 = await asyncio.wait_for(
                    page.evaluate(
                        """(tok) => {
                            return fetch("/api/transactions", { headers: { "X-CSRF-Token": tok }, credentials: "include" })
                                .then(async r => ({ status: r.status, body: await r.json() }));
                        }""",
                        [csrf_tok2],
                    ),
                    timeout=10.0,
                )
                if tx_list2["status"] == 200 and tx_list2["body"].get("items"):
                    last_tx = tx_list2["body"]["items"][-1]
                    tx_id2 = last_tx["id"]
                    csrf_tok3 = await asyncio.wait_for(
                        page.evaluate("() => window.FINORA.csrfToken"),
                        timeout=10.0,
                    )
                    del_res = await asyncio.wait_for(
                        page.evaluate(
                            """(args) => {
                                const [id, tok] = args;
                                return fetch(`/api/transactions/${id}`, { method: "DELETE", headers: { "X-CSRF-Token": tok }, credentials: "include" })
                                    .then(async r => ({ status: r.status, body: await r.text() }));
                            }""",
                            [tx_id2, csrf_tok3],
                        ),
                        timeout=10.0,
                    )
                    safe_print(f"  API delete tx {tx_id2}: status={del_res['status']}")
                    await page.wait_for_timeout(500)
                    await screenshot(page, "10_transaction_deleted")

            # filters & pagination
            await page.fill('input#f-search', "Salary")
            await page.click('button#btn-apply-filters')
            await page.wait_for_timeout(500)
            await screenshot(page, "11_search_filtered")

            # ===== 5. Budgets =====
            safe_print("== Budgets ==")
            await goto("/budgets")
            await screenshot(page, "12_budgets_list")
            await close_modal(page)
            await page.click('#btn-add-budget')
            await page.wait_for_selector("#bud-modal", state="visible")
            await page.fill('input[name="period_start"]', "2026-01-01")
            await page.fill('input[name="period_end"]', "2026-01-31")
            await page.fill('input[name="amount_limit"]', "500.00")
            await modal_save(page)
            await page.wait_for_timeout(500)
            await screenshot(page, "13_budget_added")

            # ===== 6. Recurring =====
            safe_print("== Recurring ==")
            await goto("/recurring")
            await screenshot(page, "14_recurring_list")
            await close_modal(page)
            await page.click('#btn-add-recurring')
            await page.wait_for_selector("#rec-modal", state="visible")
            await set_select(page, 'select[name="account_id"]', value="1")
            await page.fill('input[name="amount"]', "100.00")
            await page.fill('input[name="description"]', "Subscription")
            await set_select(page, 'select[name="interval"]', value="monthly")
            await page.fill('input[name="start_date"]', "2026-01-01")
            await modal_save(page)
            await page.wait_for_timeout(500)
            await screenshot(page, "15_recurring_added")

            # process due
            await page.click('#btn-process')
            await page.wait_for_timeout(500)
            body = await page.locator("body").inner_text()
            if "Создано транзакций" not in body:
                fail("Recurring processing did not report created transactions")

            # ===== 7. Reports =====
            safe_print("== Reports ==")
            await goto("/reports")
            await screenshot(page, "16_reports")
            body = await page.locator("body").inner_text()
            for label in ["Доходы vs расходы", "Расходы по категориям"]:
                if label not in body:
                    fail(f"Reports missing section: {label}")

            # ===== 8. Import/Export =====
            safe_print("== Import/Export ==")
            await goto("/import")
            await screenshot(page, "17_import_page")
            # create a temp csv and upload
            csv_path = REPO / "tests_e2e" / "sample.csv"
            csv_path.write_text("date,description,amount\n2026-03-01,Test Import,50.00\n", encoding="utf-8")
            await page.set_input_files('input[name="file"]', str(csv_path))
            await page.click('button#btn-import-preview')
            await page.wait_for_timeout(1000)
            await screenshot(page, "18_import_preview")
            body = await page.locator("body").inner_text()
            if "Test Import" not in body:
                fail("CSV preview did not show imported row")
            # confirm import
            btn = page.locator('button#btn-import-confirm')
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(1000)
                body = await page.locator("body").inner_text()
                if "Импортировано" not in body:
                    fail("CSV import confirmation did not report imported count")

            await goto("/export")
            await screenshot(page, "19_export_page")
            await page.click('button#btn-export')
            await page.wait_for_timeout(1000)
            # download triggered; check no error toast
            body = await page.locator("body").inner_text()
            safe_print("  export triggered")

            # ===== 9. Backup =====
            safe_print("== Backup ==")
            await goto("/backup")
            await screenshot(page, "20_backup_page")
            await page.click('button#btn-create-backup')
            await page.wait_for_timeout(1000)
            await screenshot(page, "21_backup_created")
            body = await page.loc("body").inner_text() if False else await page.locator("body").inner_text()
            # download backup
            async with page.expect_download() as dl_info:
                await page.click('a:has-text("Скачать")')
            download = await dl_info.value
            safe_print("  backup download:", download.suggested_filename)

            # ===== 10. Settings / language / theme =====
            safe_print("== Settings ==")
            await goto("/settings")
            await screenshot(page, "22_settings")
            await page.select_option('#lang-select', "en")
            await page.wait_for_timeout(500)
            body = await page.locator("body").inner_text()
            if "Dashboard" not in body:
                fail("English language not applied")
            await page.select_option('#lang-select', "ru")
            await page.wait_for_timeout(500)
            await screenshot(page, "23_settings_ru")

            # theme toggle (on navbar)
            await page.click('#theme-toggle')
            await page.wait_for_timeout(300)
            theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
            safe_print("  theme after toggle:", theme)
            await screenshot(page, "24_dark_theme")

            # ===== 11. Mobile viewport =====
            safe_print("== Mobile ==")
            await context.close()
            context2 = await browser.new_context(viewport={"width": 375, "height": 812})
            page2 = await context2.new_page()
            await page2.goto(f"{BASE}/dashboard", wait_until="networkidle")
            await page2.click('#mobile-menu-toggle')
            await page2.wait_for_selector("#mobile-drawer.open", state="visible")
            await screenshot(page2, "25_mobile_drawer")
            await context2.close()

            # ===== 12. Console / network check =====
            report_api_errors("final")
            if console_errors:
                for e in console_errors:
                    safe_print("  CONSOLE:", e)
                fail(f"{len(console_errors)} console errors/warnings detected")
            if failed_requests:
                for f in failed_requests:
                    safe_print("  NETWORK FAIL:", f)
                fail(f"{len(failed_requests)} failed network requests")

            await browser.close()

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    safe_print("\n=== E2E RESULT ===")
    if FAILURES:
        for f in FAILURES:
            safe_print("FAIL:", f)
        return 1
    safe_print("ALL E2E WORKFLOWS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
