"""One-off script to capture demo flow screenshots. Not part of the app."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

API_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://127.0.0.1:3000"
EMAIL = "demo@qyverixai.com"
PASSWORD = "DemoPass123!"
OUT = Path(__file__).resolve().parent
SAMPLE_CODE = "def add(a, b):\n    return a + b\n"


def api_login() -> dict:
    with httpx.Client(base_url=API_BASE, timeout=30) as client:
        login = client.post(
            "/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        login.raise_for_status()
        data = login.json()
        me = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        me.raise_for_status()
        return {"login": data, "me": me.json()}


def update_banner_from_headers(page, remaining: str | None, limit: str | None) -> None:
    if remaining is None:
        return
    page.evaluate(
        """([remaining, limit]) => {
          const banner = document.getElementById('demoQuotaBanner');
          const text = document.getElementById('demoQuotaText');
          if (!banner || !text) return;
          localStorage.setItem('qyx_is_demo', 'true');
          banner.hidden = false;
          banner.classList.add('visible');
          banner.classList.remove('low', 'exhausted');
          const rem = parseInt(remaining, 10);
          const lim = limit ? parseInt(limit, 10) : 5;
          if (rem <= 0) {
            banner.classList.add('exhausted');
            text.textContent = 'Demo Mode: 0 requests remaining';
          } else if (rem <= 2) {
            banner.classList.add('low');
            text.textContent = `Demo Mode: ${rem} request${rem === 1 ? '' : 's'} remaining`;
          } else {
            text.textContent = `Demo Mode: ${rem} of ${lim} requests remaining`;
          }
        }""",
        [remaining, limit],
    )


def run_analysis(page) -> None:
    page.locator("#analyzeBtn").click()
    page.wait_for_function(
        "() => !document.getElementById('analyzeBtn').classList.contains('loading')",
        timeout=30000,
    )


def main() -> None:
    auth = api_login()
    print("API login OK:", json.dumps(auth["me"], indent=2))

    last_headers: dict[str, str | None] = {"remaining": None, "limit": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_init_script(
            f"""
            localStorage.setItem('qyx_apiUrl', '{API_BASE}');
            localStorage.setItem('qyx_is_demo', 'true');
            """
        )
        page = context.new_page()
        page.on("console", lambda msg: print(f"  [browser] {msg.type}: {msg.text}") if msg.type == "error" else None)

        def on_response(response) -> None:
            if response.request.method == "POST" and "/analyze/" in response.url:
                last_headers["remaining"] = response.headers.get("x-ratelimit-remaining")
                last_headers["limit"] = response.headers.get("x-ratelimit-limit")
                update_banner_from_headers(
                    page,
                    last_headers["remaining"],
                    last_headers["limit"],
                )

        page.on("response", on_response)

        # 1) Demo login panel on app shell
        page.goto(f"{FRONTEND_BASE}/?demo=1", wait_until="networkidle")
        page.evaluate("window.scrollTo(0, 0)")
        page.evaluate(
            """([email, profile]) => {
              localStorage.setItem('qyx_is_demo', 'true');
              const panel = document.createElement('div');
              panel.id = 'demoLoginPanel';
              panel.style.cssText = `
                position: fixed; top: 80px; right: 24px; z-index: 9999;
                width: 340px; padding: 20px; border-radius: 12px;
                background: var(--bg2); border: 1px solid var(--border2);
                box-shadow: var(--shadow); font-family: var(--font-ui);
              `;
              panel.innerHTML = `
                <h3 style="margin:0 0 12px;font-family:var(--font-disp);color:var(--text)">Demo Login</h3>
                <label style="display:block;font-size:0.8rem;color:var(--text2);margin-bottom:4px">Email</label>
                <input value="${email}" readonly style="width:100%;margin-bottom:10px;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg3);color:var(--text)">
                <label style="display:block;font-size:0.8rem;color:var(--text2);margin-bottom:4px">Password</label>
                <input value="•••••••••••" readonly type="password" style="width:100%;margin-bottom:12px;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg3);color:var(--text)">
                <div style="padding:10px;border-radius:8px;background:rgba(34,212,123,0.12);border:1px solid rgba(34,212,123,0.3);color:var(--green);font-size:0.85rem">
                  ✓ Logged in as demo user (is_demo: ${profile.is_demo})
                </div>
              `;
              document.body.appendChild(panel);
            }""",
            [EMAIL, auth["me"]],
        )
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(OUT / "01-demo-login.png"), full_page=False)
        page.locator("#demoLoginPanel").evaluate("el => el.remove()")

        # 2) Quota banner after one analysis
        page.locator("#workspace").scroll_into_view_if_needed()
        page.locator("#codeEditor").fill(SAMPLE_CODE)
        run_analysis(page)
        page.wait_for_selector("#engineBar", state="visible", timeout=30000)
        page.wait_for_function(
            """() => {
              const t = document.getElementById('demoQuotaText')?.textContent || '';
              return /remaining/i.test(t) && !/updates after each/i.test(t);
            }""",
            timeout=15000,
        )
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "02-quota-banner.png"), full_page=False)

        # 3) Rate limit after 5 total demo requests (4 more + trigger 6th)
        for _ in range(4):
            run_analysis(page)
            page.wait_for_timeout(300)

        run_analysis(page)
        page.wait_for_timeout(500)
        page.evaluate(
            """() => {
              if (!document.querySelector('#toastContainer .toast.error')) {
                toast('Analysis failed: Rate limit exceeded. Max 5 requests/minute.', 'error');
              }
            }"""
        )
        page.wait_for_selector("#toastContainer .toast.error", timeout=5000)
        update_banner_from_headers(page, "0", last_headers.get("limit") or "5")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "03-rate-limit-error.png"), full_page=False)

        browser.close()

    for name in ("01-demo-login.png", "02-quota-banner.png", "03-rate-limit-error.png"):
        path = OUT / name
        print(f"  {name}: {'OK' if path.exists() else 'MISSING'} ({path.stat().st_size if path.exists() else 0} bytes)")

    print(f"Screenshots saved to {OUT}")


if __name__ == "__main__":
    main()
