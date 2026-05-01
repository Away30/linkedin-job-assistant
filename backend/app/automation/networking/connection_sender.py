"""LinkedIn connection request sender with personalized notes."""
import logging
from playwright.async_api import Page
from app.automation.human_simulator import HumanSimulator

logger = logging.getLogger(__name__)


class ConnectionSender:
    """Sends LinkedIn connection requests with personalized notes."""

    def __init__(self):
        self.human = HumanSimulator()

    async def send_connection(
        self, page: Page, profile_url: str, message: str
    ) -> dict:
        """Navigate to profile and send connection request with note.

        Returns: {"success": bool, "error": str | None}
        """
        try:
            await page.goto(
                profile_url, wait_until="domcontentloaded", timeout=30000
            )
            await self.human.random_delay(3, 6)

            # Click Connect button
            connect_btn = await self._find_connect_button(page)
            if not connect_btn:
                return {
                    "success": False,
                    "error": "No Connect button (already connected or restricted)",
                }
            await self.human.human_click(connect_btn)
            await self.human.random_delay(1, 3)

            # Check for "Add a note" modal option
            add_note_btn = await page.query_selector(
                'button:has-text("Add a note")'
            )
            if add_note_btn:
                await self.human.human_click(add_note_btn)
                await self.human.random_delay(1, 2)

                # Fill note textarea
                note_input = await page.query_selector(
                    '#custom-message, textarea[name="message"], textarea'
                )
                if note_input:
                    await note_input.click()
                    await note_input.fill("")
                    await self.human.type_like_human(note_input, message[:300])
                    await self.human.random_delay(1, 2)

                # Click Send
                send_btn = await page.query_selector(
                    'button:has-text("Send"), button[aria-label="Send now"]'
                )
                if send_btn:
                    await self.human.human_click(send_btn)
                    await self.human.random_delay(2, 4)
                    return {"success": True, "error": None}
                else:
                    return {
                        "success": False,
                        "error": "Send button not found in note modal",
                    }
            else:
                # Direct connect without note — check for confirm
                send_btn = await page.query_selector(
                    'button:has-text("Send"), button:has-text("Done")'
                )
                if send_btn:
                    await self.human.human_click(send_btn)
                    await self.human.random_delay(1, 3)
                    return {"success": True, "error": None}

                # May have already connected without note
                return {
                    "success": False,
                    "error": "Unexpected state after Connect click",
                }

        except Exception as e:
            logger.warning("send_connection failed: %s", e)
            return {"success": False, "error": str(e)}

    async def _find_connect_button(self, page: Page):
        """Find the Connect button on a LinkedIn profile page."""
        selectors = [
            # Top card action buttons
            'button:has-text("Connect")',
            '[aria-label="Connect"]',
            "[data-test-icon='connect-small']",
            ".pv-s-profile-actions--connect",
            'button[data-control-name="connect"]',
            'button[class*="connect"]',
            # More actions menu → Connect
            'div[class*="pv-top-card"] button:has-text("Connect")',
            # Action overflow menu
            '.pv-top-card-v2-ctas button:has-text("Connect")',
        ]
        for sel in selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    return btn
            except Exception:
                continue

        # Fallback: scan all visible buttons for "Connect" text
        try:
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                try:
                    if await btn.is_visible():
                        text = (await btn.inner_text()).strip().lower()
                        if text == "connect":
                            return btn
                except Exception:
                    continue
        except Exception:
            pass

        return None
