#!/usr/bin/env python3
"""
Passive Human-Controlled Capture for GEL Tutorial Deletion.
Workflow:
1. Opens a visible Chromium browser.
2. User manually logs in and navigates to the student profile.
3. User signals the script to capture the PRE-DELETE state.
4. User manually performs the destructive delete action (clicks trash can, confirms).
5. User signals the script to capture the POST-DELETE state and finish.
6. Script saves a comprehensive JSON log of all network traffic, UI interactions, dialogs, and DOM states.
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
from playwright.async_api import async_playwright, Page

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
POSTAL_RE = re.compile(r"\b(?:[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d ()\-.]{7,}\d)(?!\d)")

class Anonymizer:
    def __init__(self) -> None:
        self.names: dict[str, str] = {}

    def alias_name(self, value: str) -> str:
        key = " ".join(value.split())
        if not key: return value
        if key not in self.names:
            self.names[key] = f"Teacher_{len(self.names) + 1:03d}"
        return self.names[key]

    def text(self, value: str) -> str:
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
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))

def sanitize_headers(headers: dict[str, str], anon: Anonymizer) -> dict[str, str]:
    keep = {}
    for key, value in headers.items():
        lk = key.lower()
        if lk in {"cookie", "authorization", "proxy-authorization", "set-cookie"}:
            continue
        keep[key] = anon.text(value)
    return keep

async def capture_dom_state(page: Page, anon: Anonymizer) -> dict:
    """Captures a privacy-scrubbed snapshot of the page's text content."""
    body_text = ""
    try:
        body_text = anon.text((await page.locator("body").inner_text())[:30000])
    except Exception:
        pass
    return {
        "url": safe_url(page.url),
        "title": anon.text(await page.title()),
        "bodyTextPreview": body_text,
    }

async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://staff2.guidedelearning.net/students/2514/464952/profile")
    parser.add_argument("--output", default="gel_tutorial_delete_capture.json")
    args = parser.parse_args()
    
    anon = Anonymizer()
    
    # Storage for all captured data
    requests_log = []
    responses_log = []
    dialogs_log = []
    console_log = []
    user_interactions = [] # Stores clicks and keypresses
    request_map = {} # To link requests and responses

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # --- INJECT INTERACTION TRACKER ---
        # This logs every click the user makes to the console so we can record it
        await page.add_init_script("""
            document.addEventListener('click', (e) => {
                const t = e.target;
                // Walk up to find the nearest button or link if the click was on an SVG/icon
                let targetEl = t;
                for (let i = 0; i < 5; i++) {
                    if (targetEl.tagName === 'BUTTON' || targetEl.tagName === 'A' || targetEl.getAttribute('role') === 'button') break;
                    if (targetEl.parentElement) targetEl = targetEl.parentElement;
                    else break;
                }
                console.log('[USER_CLICK]', JSON.stringify({
                    tag: targetEl.tagName,
                    id: targetEl.id,
                    class: targetEl.className,
                    text: (targetEl.innerText || '').substring(0, 50),
                    ariaLabel: targetEl.getAttribute('aria-label'),
                    originalTag: t.tagName
                }));
            }, true);
        """)

        # --- EVENT LISTENERS ---
        page.on("console", lambda msg: (
            user_interactions.append({"type": "click", "data": json.loads(msg.text.replace('[USER_CLICK] ', '')), "timestamp": time.time()})
            if msg.text.startswith('[USER_CLICK]') 
            else console_log.append({"type": msg.type, "text": anon.text(msg.text)})
        ))
        
        page.on("dialog", lambda dialog: (
            dialogs_log.append({
                "type": dialog.type,
                "message": anon.text(dialog.message),
                "defaultValue": anon.text(dialog.default_value or ""),
                "timestamp": time.time()
            }) or dialog.dismiss() # Dismiss alerts/prompts but log them. For confirms, you might want to handle manually, but dismiss is safe for logging.
        ))

        async def on_request(req):
            rid = id(req)
            item = {
                "id": rid,
                "method": req.method,
                "url": safe_url(req.url),
                "resourceType": req.resource_type,
                "headers": sanitize_headers(await req.all_headers(), anon),
                "timestamp": time.time()
            }
            try:
                post = req.post_data
                if post: item["postData"] = anon.text(post)
            except Exception: pass
            request_map[rid] = item
            requests_log.append(item)

        async def on_response(resp):
            req = resp.request
            rid = id(req)
            if rid not in request_map: return
            
            item = {
                "requestId": rid,
                "method": req.method,
                "url": safe_url(req.url),
                "status": resp.status,
                "statusText": resp.status_text,
                "headers": sanitize_headers(await resp.all_headers(), anon),
                "timestamp": time.time()
            }
            # Capture body for API responses
            if req.resource_type in {"xhr", "fetch"}:
                try:
                    ct = (await resp.all_headers()).get("content-type", "").lower()
                    if "application/json" in ct:
                        item["bodyPreview"] = anon.text((await resp.text())[:12000])
                except Exception: pass
            responses_log.append(item)

        page.on("request", on_request)
        page.on("response", on_response)

        # --- EXECUTION FLOW ---
        print(f"Opening browser to: {args.url}")
        await page.goto(args.url, wait_until="domcontentloaded")
        
        print("\n" + "="*60)
        print("STEP 1: MANUAL NAVIGATION")
        print("="*60)
        print("Please log in and navigate to the student profile manually.")
        print("Ensure you are on the page with the 'Last 4 tutorials' list.")
        input("\n>>> Press ENTER here when you are ready to capture the PRE-DELETE state...")
        
        pre_state = await capture_dom_state(page, anon)
        print("[OK] Pre-delete state captured.")

        print("\n" + "="*60)
        print("STEP 2: MANUAL DELETION")
        print("="*60)
        print("Now, manually perform the DELETE action in the browser:")
        print("1. Click the trash can icon next to the tutorial.")
        print("2. Click 'Yes' on the confirmation dialog.")
        print("\nTake your time. The script is recording all clicks and network requests.")
        input("\n>>> Press ENTER here when the deletion is complete...")
        
        post_state = await capture_dom_state(page, anon)
        print("[OK] Post-delete state captured.")

        # --- SAVE DATA ---
        output = {
            "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target": {"profileUrl": safe_url(args.url)},
            "preClick": pre_state,
            "postClick": post_state,
            "userInteractions": user_interactions,
            "dialogs": dialogs_log,
            "requests": requests_log,
            "responses": responses_log,
            "console": console_log,
            "privacy": {
                "emails": "replaced with email@email.com",
                "student_names": "stable aliases where paired with an email",
                "postal_addresses": "redacted where recognised",
                "credentials_and_cookies": "not retained",
            },
            "nameAliases": anon.names,
        }
        
        output = anon.recursive(output)
        output_path = Path(args.output)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        
        print(f"\n[SUCCESS] Comprehensive capture saved to: {output_path.resolve()}")
        await browser.close()
        return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))