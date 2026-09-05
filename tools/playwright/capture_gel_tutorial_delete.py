#!/usr/bin/env python3
"""
Capture the real GEL tutorial-delete interaction.

Workflow:
  1. Open a visible Chromium browser at the staff2 student profile page.
  2. User logs in manually if required.
  3. User selects a tutorial row and clicks its delete icon.
  4. Capture the delete control DOM/attributes, all requests/responses caused by
     the click, dialogs, and the post-click UI state.
  5. Write privacy-scrubbed JSON. Student names are stable aliases and emails /
     postal addresses are removed or replaced.

Usage:
  python capture_gel_tutorial_delete.py \
      --url 'https://staff2.guidedelearning.net/students/2514/464952/profile'

Optional:
  --output capture_delete.json
  --wait-after-click 2500
  --no-click   only inspect the page and controls

IMPORTANT: Use a tutorial that is safe to delete. The script does NOT attempt
            to undo deletion.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import async_playwright, Page, Locator


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
POSTAL_RE = re.compile(
    r"\b(?:[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.I
)
# Common phone-like strings are scrubbed as well because they are unnecessary
# for establishing the delete contract.
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d ()\-.]{7,}\d)(?!\d)")


class Anonymizer:
    def __init__(self) -> None:
        self.names: dict[str, str] = {}

    def alias_name(self, value: str) -> str:
        key = " ".join(value.split())
        if not key:
            return value
        if key not in self.names:
            self.names[key] = f"Teacher_{len(self.names) + 1:03d}"
        return self.names[key]

    def text(self, value: str) -> str:
        # Replace email-bearing "Name email" strings first. This handles
        # multiple names such as "Mary Jane Smith email@example.com" as one
        # name rather than trying to split it into first/last names.
        email = EMAIL_RE.search(value)
        if email:
            before = value[: email.start()].strip()
            after = value[email.end() :]
            if before:
                return self.alias_name(before) + " email@email.com" + after
            return value[: email.start()] + "email@email.com" + after

        value = EMAIL_RE.sub("email@email.com", value)
        value = POSTAL_RE.sub("[POSTAL-REDACTED]", value)
        value = PHONE_RE.sub("[PHONE-REDACTED]", value)
        return value

    def recursive(self, value):
        if isinstance(value, dict):
            return {k: self.recursive(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.recursive(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def safe_url(url: str) -> str:
    """Keep URL structure; do not retain query strings/fragments that may
    contain search terms or PII."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def sanitize_headers(headers: dict[str, str], anon: Anonymizer) -> dict[str, str]:
    keep = {}
    for key, value in headers.items():
        lk = key.lower()
        # Never retain credentials/session material.
        if lk in {"cookie", "authorization", "proxy-authorization", "set-cookie"}:
            continue
        keep[key] = anon.text(value)
    return keep


async def attr_snapshot(locator: Locator) -> list[dict]:
    count = await locator.count()
    out = []
    for i in range(min(count, 100)):
        el = locator.nth(i)
        try:
            out.append({
                "tag": await el.evaluate("e => e.tagName.toLowerCase()"),
                "text": (await el.inner_text())[:500],
                "outerHTML": (await el.evaluate("e => e.outerHTML"))[:4000],
            })
        except Exception:
            pass
    return out


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="https://staff2.guidedelearning.net/students/2514/464952/profile",
    )
    parser.add_argument("--output", default="gel_tutorial_delete_capture.json")
    parser.add_argument("--wait-after-click", type=int, default=2500)
    parser.add_argument("--no-click", action="store_true")
    args = parser.parse_args()

    anon = Anonymizer()
    events: list[dict] = []
    dialog_events: list[dict] = []
    requests: dict[int, dict] = {}
    responses: list[dict] = []
    failures: list[dict] = []
    console: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Capture page-side console errors without retaining arbitrary page data.
        page.on("console", lambda msg: console.append({
            "type": msg.type,
            "text": anon.text(msg.text),
        }))
        page.on("requestfailed", lambda req: failures.append({
            "method": req.method,
            "url": safe_url(req.url),
            "failure": anon.text(req.failure or ""),
            "resourceType": req.resource_type,
        }))

        async def on_request(req):
            if req.resource_type in {"xhr", "fetch", "document", "script"} or req.method not in {"GET", "HEAD"}:
                rid = id(req)
                item = {
                    "method": req.method,
                    "url": safe_url(req.url),
                    "resourceType": req.resource_type,
                    "headers": sanitize_headers(await req.all_headers(), anon),
                }
                # Capture form/query payload only after scrubbing it. We do not
                # retain cookies/auth headers.
                try:
                    post = req.post_data
                    if post:
                        item["postData"] = anon.text(post)
                except Exception:
                    pass
                requests[rid] = item

        async def on_response(resp):
            req = resp.request
            if id(req) not in requests:
                return
            item = {
                "method": req.method,
                "url": safe_url(req.url),
                "status": resp.status,
                "statusText": resp.status_text,
                "headers": sanitize_headers(await resp.all_headers(), anon),
                "resourceType": req.resource_type,
            }
            # For likely mutation responses, retain only bounded, scrubbed text.
            # This is useful for distinguishing redirects/JSON success/error
            # without retaining an entire HTML page.
            if req.method not in {"GET", "HEAD"} or req.resource_type in {"xhr", "fetch"}:
                try:
                    ct = (await resp.all_headers()).get("content-type", "").lower()
                    if "application/json" in ct:
                        body = await resp.text()
                        item["bodyPreview"] = anon.text(body[:12000])
                    elif "text/plain" in ct:
                        body = await resp.text()
                        item["bodyPreview"] = anon.text(body[:4000])
                except Exception as exc:
                    item["bodyReadError"] = type(exc).__name__
            responses.append(item)

        page.on("request", on_request)
        page.on("response", on_response)

        async def on_dialog(dialog):
            # Do not accept/dismiss automatically. Capture the message and let
            # the user make the destructive decision in the browser.
            dialog_events.append({
                "type": dialog.type,
                "message": anon.text(dialog.message),
                "defaultValue": anon.text(dialog.default_value or ""),
            })
            if dialog.type in {"alert", "confirm", "prompt"}:
                await dialog.dismiss()

        page.on("dialog", on_dialog)

        print("Opening authenticated GEL page:")
        print(f"  {args.url}")
        await page.goto(args.url, wait_until="domcontentloaded")

        print("\nLog in manually if required.")
        print("Do not enter credentials into this script.")
        print("When the student profile and tutorial list are visible, press ENTER here.")
        await asyncio.to_thread(input)

        # Snapshot the page structure around likely tutorial/delete controls.
        # We deliberately inspect common delete representations rather than
        # assuming one specific CSS class.
        selectors = [
            "button",
            "a",
            "[role=button]",
            "input[type=button]",
            "input[type=submit]",
            "[data-action]",
            "[data-delete]",
            "[onclick*='delete' i]",
            "[href*='delete' i]",
        ]
        controls = {}
        for selector in selectors:
            try:
                controls[selector] = await attr_snapshot(page.locator(selector))
            except Exception:
                controls[selector] = []

        # Extract a privacy-safe body text snapshot for identifying tutorial
        # rows and the post-delete state. Do not retain arbitrary page HTML.
        body_text = ""
        try:
            body_text = anon.text((await page.locator("body").inner_text())[:30000])
        except Exception:
            pass

        pre_state = {
            "url": safe_url(page.url),
            "title": anon.text(await page.title()),
            "bodyTextPreview": body_text,
            "deleteControlCandidates": controls,
        }

        print("\nCandidate delete controls have been captured.")
        if args.no_click:
            clicked = False
        else:
            print("\nIMPORTANT: the next action is destructive.")
            print("Select the tutorial you intend to delete in the browser.")
            print("Then press ENTER here; the script will enumerate likely delete controls.")
            await asyncio.to_thread(input)

            # Do not guess which tutorial to delete. The user must explicitly
            # identify the target via a visible marker in the browser. We expose
            # a small interactive list of likely controls based on their text.
            candidates = []
            for selector in ["button", "a", "[role=button]", "[data-action]", "[data-delete]", "[onclick*='delete' i]", "[href*='delete' i]"]:
                loc = page.locator(selector)
                count = await loc.count()
                for i in range(min(count, 200)):
                    el = loc.nth(i)
                    try:
                        text = anon.text((await el.inner_text())[:300])
                        attrs = await el.evaluate("e => Object.fromEntries([...e.attributes].map(a => [a.name, a.value]))")
                        hay = json.dumps(attrs, ensure_ascii=False).lower() + " " + text.lower()
                        if "delete" in hay or "remove" in hay or "trash" in hay:
                            candidates.append((selector, i, text, attrs))
                    except Exception:
                        continue

            if not candidates:
                print("No obvious delete control was found.")
                print("The pre-click DOM snapshot has still been saved.")
                clicked = False
            else:
                print("\nLikely delete controls:")
                for n, (selector, idx, text, attrs) in enumerate(candidates):
                    print(f"  [{n}] {selector} #{idx} text={text!r}")
                    interesting = {k: v for k, v in attrs.items() if k in {"id", "class", "href", "onclick", "title", "aria-label", "data-action", "data-delete", "data-id"}}
                    if interesting:
                        print(f"      {interesting}")
                print("\nEnter the number of the DELETE control to click, or 'q' to abort.")
                choice = (await asyncio.to_thread(input)).strip()
                if choice.lower() == "q":
                    clicked = False
                else:
                    try:
                        n = int(choice)
                        selector, idx, _, _ = candidates[n]
                    except (ValueError, IndexError):
                        print("Invalid choice; nothing clicked.")
                        clicked = False
                    else:
                        target = page.locator(selector).nth(idx)
                        # Capture exact target DOM immediately before clicking.
                        target_snapshot = {
                            "selector": selector,
                            "index": idx,
                            "outerHTML": (await target.evaluate("e => e.outerHTML"))[:10000],
                            "attributes": await target.evaluate("e => Object.fromEntries([...e.attributes].map(a => [a.name, a.value]))"),
                            "text": anon.text((await target.inner_text())[:1000]),
                        }
                        events.append({"type": "delete-control-selected", "control": target_snapshot})

                        print("Clicking selected delete control...")
                        # Clear request/response capture so we can isolate the
                        # interaction from initial page loading.
                        requests.clear()
                        responses.clear()
                        failures.clear()
                        dialog_events.clear()
                        start = time.time()
                        try:
                            await target.click()
                            clicked = True
                        except Exception as exc:
                            clicked = False
                            events.append({"type": "click-error", "error": type(exc).__name__ + ": " + str(exc)[:500]})

                        await page.wait_for_timeout(args.wait_after_click)
                        events.append({
                            "type": "delete-click-complete",
                            "elapsedMs": round((time.time() - start) * 1000),
                        })

        post_body = ""
        try:
            post_body = anon.text((await page.locator("body").inner_text())[:30000])
        except Exception:
            pass

        post_state = {
            "url": safe_url(page.url),
            "title": anon.text(await page.title()),
            "bodyTextPreview": post_body,
        }

        output = {
            "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target": {
                "profileUrl": safe_url(args.url),
                "clicked": clicked,
            },
            "preClick": pre_state,
            "events": events,
            "dialogs": dialog_events,
            "requests": list(requests.values()),
            "responses": responses,
            "requestFailures": failures,
            "console": console,
            "postClick": post_state,
            "privacy": {
                "emails": "replaced with email@email.com",
                "student_names": "stable aliases where paired with an email",
                "postal_addresses": "redacted where recognised",
                "credentials_and_cookies": "not retained",
            },
            "nameAliases": anon.names,
        }

        # Second recursive scrub catches PII introduced in attributes or event
        # fields not handled by the targeted scrubbers above.
        output = anon.recursive(output)

        output_path = Path(args.output)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nSaved capture to {output_path.resolve()}")

        await browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
