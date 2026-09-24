"""Run browser acceptance checks in an isolated temporary database; capture demo screenshots."""
import os
import secrets
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import WSGIRequestHandler, make_server

from app import create_app
from app.extensions import db


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def main():
    root = Path(__file__).resolve().parents[1]
    screenshots = root / "docs" / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mindcare-browser-") as temporary:
        app = create_app({"TESTING": True, "SECRET_KEY": secrets.token_hex(32), "PRODUCTION": False,
                          "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(Path(temporary) / "browser.db").replace("\\", "/"),
                          "SESSION_COOKIE_SECURE": False})
        server = make_server("127.0.0.1", 5051, app, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                chrome_path = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
                browser = playwright.chromium.launch(executable_path=str(chrome_path) if chrome_path.exists() else None, headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                base = "http://127.0.0.1:5051"
                page.goto(base)
                expect(page.get_by_role("heading", name="Talk. Reflect. Feel Supported.")).to_be_visible()
                page.screenshot(path=str(screenshots / "home.png"), full_page=True)
                page.get_by_role("link", name="Get started").click()
                password = secrets.token_urlsafe(20)
                page.get_by_label("Full name", exact=True).fill("Alex Rivera")
                page.get_by_label("Username", exact=True).fill("alex_demo")
                page.get_by_label("Email address", exact=True).fill("alex@example.com")
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_label("Confirm password", exact=True).fill(password)
                page.get_by_role("button", name="Show password", exact=True).click()
                expect(page.get_by_label("Password", exact=True)).to_have_attribute("type", "text")
                page.get_by_role("button", name="Create account", exact=True).click()
                expect(page).to_have_url(base + "/login")
                page.get_by_label("Email or username").fill("alex_demo")
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Log in", exact=True).click()
                expect(page.get_by_role("heading", name="How are you feeling today?")).to_be_visible()
                expect(page.locator("#new-conversation")).to_be_enabled()
                page.screenshot(path=str(screenshots / "chat-empty.png"), full_page=True)

                page.get_by_role("button", name="A lot on my mind").click()
                expect(page.get_by_label("Your message")).to_have_value("I've been feeling stressed lately.")
                pending_requests = []
                page.route("**/api/chat", lambda route: pending_requests.append(route))
                page.get_by_label("Your message").fill("I feel stressed because of my exams.")
                with page.expect_request("**/api/chat"):
                    page.get_by_label("Your message").press("Enter")
                expect(page.locator(".typing")).to_be_visible()
                expect(page.get_by_role("button", name="Send message", exact=True)).to_be_disabled()
                pending_requests[0].continue_()
                page.unroute("**/api/chat")
                expect(page.locator(".message-bot")).to_have_count(1)
                expect(page.locator(".resource-card")).to_have_count(3)
                expect(page.locator(".sentiment-badge")).to_have_text("Negative")
                expect(page.locator("#new-conversation")).to_be_enabled()
                first_url = page.url
                page.locator(".analysis summary").click()
                expect(page.locator(".analysis p")).to_contain_text("study")
                for link in page.locator(".resource-card").all():
                    assert link.get_attribute("href").startswith("https://www.youtube.com/results?")
                    assert link.get_attribute("target") == "_blank"
                    assert link.get_attribute("rel") == "noopener noreferrer"
                page.screenshot(path=str(screenshots / "chat-resources.png"), full_page=True)
                page.reload()
                expect(page.locator(".message")).to_have_count(2)
                expect(page.locator(".resource-card")).to_have_count(3)

                page.get_by_role("button", name="New conversation", exact=True).click()
                expect(page.locator("#message-input")).to_be_enabled()
                expect(page.locator("#empty-state")).to_be_visible()
                page.get_by_label("Your message").fill("I feel amazing today")
                page.get_by_label("Your message").press("Enter")
                expect(page.locator(".sentiment-badge")).to_have_text("Positive")
                expect(page.locator("#new-conversation")).to_be_enabled()
                page.get_by_role("button", name="Study & Exam Reflection", exact=True).click()
                expect(page).to_have_url(first_url)
                expect(page.locator(".message")).to_have_count(2)

                # Rendering uses textContent: HTML-like chat input must remain inert.
                page.get_by_label("Your message").fill('<img src=x onerror="window.xss=1">')
                page.get_by_label("Your message").press("Enter")
                expect(page.locator(".message-bot")).to_have_count(2)
                assert page.locator(".messages img").count() == 0
                assert page.evaluate("window.xss") is None
                expect(page.locator("#new-conversation")).to_be_enabled()

                # Safety responses have no ordinary resource cards for that turn.
                page.get_by_label("Your message").fill("I am going to hurt myself tonight")
                page.get_by_label("Your message").press("Enter")
                expect(page.locator(".safety-notice")).to_be_visible()
                expect(page.locator(".message-bot").last.locator(".resource-card")).to_have_count(0)
                expect(page.locator("#new-conversation")).to_be_enabled()

                # An interrupted request must preserve the draft and release the composer.
                page.route("**/api/chat", lambda route: route.abort("failed"))
                page.get_by_label("Your message").fill("A message for retry")
                page.get_by_label("Your message").press("Enter")
                expect(page.locator("#chat-error")).to_be_visible()
                expect(page.get_by_label("Your message")).to_be_enabled()
                expect(page.get_by_label("Your message")).to_have_value("A message for retry")
                page.unroute("**/api/chat")
                # Chrome reports an expected net::ERR_FAILED for the intentionally aborted request.
                errors = [error for error in errors if "net::ERR_FAILED" not in error]

                page.get_by_role("button", name="New conversation", exact=True).click()
                expect(page.locator("#new-conversation")).to_be_enabled()
                page.set_viewport_size({"width": 390, "height": 844})
                expect(page.locator("#open-sidebar")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshots / "mobile-chat.png"), full_page=True)
                page.get_by_role("button", name="Open conversation menu").click()
                expect(page.locator("#sidebar")).to_have_class("sidebar is-open")
                page.get_by_role("button", name="Delete New Conversation", exact=True).click()
                expect(page.locator("#delete-dialog")).to_be_visible()
                page.get_by_role("button", name="Keep conversation").click()
                expect(page.locator("#delete-dialog")).not_to_be_visible()
                page.get_by_role("button", name="Delete New Conversation", exact=True).click()
                page.get_by_role("button", name="Delete conversation", exact=True).click()
                expect(page.get_by_role("button", name="Delete New Conversation", exact=True)).to_have_count(0)
                page.locator("#close-sidebar").click()
                expect(page.locator("#open-sidebar")).to_have_attribute("aria-expanded", "false")
                page.get_by_label("Your message").fill("I went to college today")
                page.get_by_label("Your message").press("Shift+Enter")
                expect(page.get_by_label("Your message")).to_have_value("I went to college today\n")
                page.get_by_label("Your message").press("Enter")
                expect(page.locator(".sentiment-badge")).to_have_text("Neutral")
                expect(page.locator("#new-conversation")).to_be_enabled()
                page.get_by_role("button", name="Open conversation menu").click()
                page.get_by_role("button", name="Log out", exact=True).click()
                expect(page).to_have_url(base + "/")
                page.goto(base + "/chat")
                expect(page).to_have_url(base + "/login")
                for width in (320, 768):
                    page.set_viewport_size({"width": width, "height": 844})
                    for path in ("/", "/about", "/register", "/login"):
                        page.goto(base + path)
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (width, path)
                assert not errors, errors
                print("Browser checks passed: registration, login, password toggle, AJAX chat, sentiments, resources, history, XSS, safety, network recovery, mobile drawer, deletion, logout. No unexpected browser console errors.")
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    main()
