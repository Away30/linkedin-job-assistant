"""Human-like behavior simulation for anti-detection."""
import asyncio
import logging
import random
import math
from typing import Optional
from playwright.async_api import Page, Locator

logger = logging.getLogger(__name__)


class HumanSimulator:
    """Simulates human-like interactions to avoid bot detection."""

    def __init__(self, action_delay_min: float = 3.0, action_delay_max: float = 12.0):
        self.action_delay_min = action_delay_min
        self.action_delay_max = action_delay_max
        self._mouse_x: float = 0.0
        self._mouse_y: float = 0.0

    async def random_delay(self, min_s: Optional[float] = None, max_s: Optional[float] = None):
        """Wait a random duration using gaussian distribution."""
        min_s = min_s or self.action_delay_min
        max_s = max_s or self.action_delay_max
        mean = (min_s + max_s) / 2
        std = (max_s - min_s) / 4
        delay = max(min_s, min(max_s, random.gauss(mean, std)))
        await asyncio.sleep(delay)

    async def short_delay(self):
        """Brief pause between sub-actions (0.5-2s)."""
        await asyncio.sleep(random.uniform(0.5, 2.0))

    async def type_like_human(self, locator: Locator, text: str):
        """Type text with random delays between keystrokes."""
        await locator.click()
        await self.short_delay()
        delay = random.randint(50, 150)
        if len(text) > 6 and random.random() < 0.3:
            split = random.randint(len(text) // 3, 2 * len(text) // 3)
            await locator.press_sequentially(text[:split], delay=delay)
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await locator.press_sequentially(text[split:], delay=delay)
        else:
            await locator.press_sequentially(text, delay=delay)

    async def human_click(self, locator: Locator):
        """Click with slight position randomness and pre/post delays."""
        await asyncio.sleep(random.uniform(0.3, 1.0))
        try:
            box = await locator.bounding_box()
            if box:
                x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                page = locator.page
                await page.mouse.click(x, y)
            else:
                await locator.click()
        except Exception as e:
            logger.debug("human_click fallback for locator: %s", e)
            await locator.click()
        await asyncio.sleep(random.uniform(0.2, 0.6))

    async def scroll_naturally(self, page: Page, direction: str = "down", distance: int = 300):
        """Scroll with variable speed to simulate human reading."""
        steps = random.randint(3, 8)
        step_distance = distance // steps
        for _ in range(steps):
            delta = step_distance * (1 if direction == "down" else -1)
            await page.mouse.wheel(0, delta)
            await asyncio.sleep(random.uniform(0.1, 0.4))

    async def maybe_long_break(self, probability: float = 0.05):
        """Occasionally take a longer break (30-120s) to appear more human."""
        if random.random() < probability:
            duration = random.uniform(30, 120)
            await asyncio.sleep(duration)
            return True
        return False

    async def move_mouse_naturally(self, page: Page, target_x: float, target_y: float):
        """Move mouse in a curved path from current position to target."""
        current_x = self._mouse_x
        current_y = self._mouse_y

        steps = random.randint(10, 25)

        # Add control point for bezier-like curve
        ctrl_x = (current_x + target_x) / 2 + random.uniform(-100, 100)
        ctrl_y = (current_y + target_y) / 2 + random.uniform(-50, 50)

        for i in range(steps + 1):
            t = i / steps
            # Quadratic bezier
            x = (1-t)**2 * current_x + 2*(1-t)*t * ctrl_x + t**2 * target_x
            y = (1-t)**2 * current_y + 2*(1-t)*t * ctrl_y + t**2 * target_y
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.01, 0.05))

        self._mouse_x = target_x
        self._mouse_y = target_y
