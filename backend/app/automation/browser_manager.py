"""Playwright browser lifecycle management with stealth and CDP support."""
import asyncio
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from app.config import settings

logger = logging.getLogger(__name__)


def _find_chrome_executable() -> str:
    """Find system Chrome executable."""
    # macOS
    mac_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for p in mac_paths:
        if Path(p).exists():
            return p
    # Linux
    for name in ("google-chrome", "chromium-browser", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    # Windows
    win_paths = [
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    for p in win_paths:
        if p.exists():
            return str(p)
    raise FileNotFoundError("找不到 Chrome，请安装 Google Chrome")


class BrowserManager:
    """Manages Playwright browser with CDP or persistent context."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_running = False
        self._using_cdp = False
        self._chrome_process = None  # Auto-started Chrome process

    @property
    def is_running(self) -> bool:
        return self._is_running and (self._context is not None or self._browser is not None)

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def launch(self, headless: bool = False) -> Page:
        """Launch or connect to browser."""
        if self.is_running:
            return self._page

        # Try connecting to user's existing Chrome via CDP
        if settings.USE_CDP:
            try:
                return await self._connect_cdp()
            except Exception as e:
                logger.warning("CDP 直连失败，尝试自动启动 Chrome: %s", e)
                # Auto-start Chrome with debug port, then retry CDP
                try:
                    await self._auto_start_chrome()
                    await asyncio.sleep(2)  # Wait for Chrome to start
                    return await self._connect_cdp()
                except Exception as e2:
                    logger.warning("自动启动 Chrome 也失败，回退到 Playwright 浏览器: %s", e2)

        # Fallback: launch Playwright's own browser
        try:
            return await self._launch_new_browser(headless)
        except Exception as e:
            error_msg = str(e)
            if "Executable doesn't exist" in error_msg or "playwright install" in error_msg.lower():
                raise RuntimeError(
                    "Playwright 浏览器未安装。请运行: playwright install chromium\n"
                    "或使用 scripts/setup.sh 一键安装。"
                ) from e
            raise

    async def _auto_start_chrome(self):
        """Auto-start system Chrome with remote debugging port."""
        chrome_path = _find_chrome_executable()
        profile_dir = str(settings.DATA_DIR / "chrome_profile")
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        cmd = [
            chrome_path,
            f"--remote-debugging-port=9222",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        logger.info("自动启动 Chrome: %s", " ".join(cmd))
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Detach from parent process so it survives backend shutdown
            start_new_session=True,
        )
        self._chrome_process = process
        logger.info("Chrome 已启动 (PID: %d, 调试端口: 9222)", process.pid)

    async def _connect_cdp(self) -> Page:
        """Connect to user's existing Chrome via Chrome DevTools Protocol."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(
            settings.CDP_ENDPOINT
        )

        # Get existing context and pages
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()
        else:
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

        # Apply stealth scripts
        await self._apply_stealth(self._context)

        self._is_running = True
        self._using_cdp = True
        logger.info("已通过 CDP 连接到用户现有 Chrome")
        return self._page

    async def _launch_new_browser(self, headless: bool = False) -> Page:
        """Launch a new browser with persistent profile (original behavior)."""
        profile_dir = str(settings.BROWSER_PROFILE_DIR)
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        launch_kwargs = dict(
            user_data_dir=profile_dir,
            headless=headless,
            viewport={"width": 1366, "height": 768},
            user_agent=settings.BROWSER_USER_AGENT,
            locale="en-US",
            timezone_id="America/New_York",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
        )

        # Add proxy if configured
        if settings.PROXY_SERVER:
            launch_kwargs["proxy"] = {"server": settings.PROXY_SERVER}
            if settings.PROXY_USERNAME:
                launch_kwargs["proxy"]["username"] = settings.PROXY_USERNAME
                launch_kwargs["proxy"]["password"] = settings.PROXY_PASSWORD
            logger.info("使用代理: %s", settings.PROXY_SERVER)

        self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Apply stealth scripts
        await self._apply_stealth(self._context)

        # Use existing page or create new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        self._is_running = True
        self._using_cdp = False
        logger.info("已启动新浏览器实例")
        return self._page

    async def _apply_stealth(self, context: BrowserContext):
        """Apply comprehensive anti-detection measures."""
        await context.add_init_script("""
            // Fix webdriver — must return false, not undefined
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: true,
            });

            // Realistic plugins array (PluginArray-like with Plugin objects)
            const fakePluginArray = [
                {
                    name: 'Chrome PDF Plugin',
                    filename: 'internal-pdf-viewer',
                    description: 'Portable Document Format',
                    length: 1,
                    0: { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                },
                {
                    name: 'Chrome PDF Viewer',
                    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                    description: '',
                    length: 1,
                    0: { type: 'application/pdf', suffixes: 'pdf', description: '' },
                },
                {
                    name: 'Native Client',
                    filename: 'internal-nacl-plugin',
                    description: '',
                    length: 2,
                    0: { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' },
                    1: { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' },
                },
            ];
            // Make it look like PluginArray
            fakePluginArray.item = function(i) { return this[i]; };
            fakePluginArray.namedItem = function(name) { return this.find(p => p.name === name) || null; };
            fakePluginArray.refresh = function() {};
            Object.defineProperty(navigator, 'plugins', {
                get: () => fakePluginArray,
                configurable: true,
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true,
            });

            // Chrome runtime (full object)
            if (!window.chrome) {
                window.chrome = {};
            }
            if (!window.chrome.runtime) {
                window.chrome.runtime = {
                    connect: function() {},
                    sendMessage: function() {},
                    onMessage: { addListener: function() {}, removeListener: function() {} },
                    id: undefined,
                };
            }

            // Permissions
            const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(parameters);

            // Hide Playwright artifacts
            delete window.__playwright_evaluation_script__;

            // Override iframe contentWindow detection
            const origGetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get;
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    const win = origGetter.call(this);
                    if (win) {
                        try { delete win.navigator.webdriver; } catch(e) {}
                    }
                    return win;
                },
            });

            // Consistent hardware info
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true,
            });
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true,
            });

            // WebGL vendor/renderer masking
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return 'Google Inc. (NVIDIA)';
                if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060, OpenGL 4.5)';
                return getParameter.call(this, param);
            };
            if (typeof WebGL2RenderingContext !== 'undefined') {
                const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(param) {
                    if (param === 37445) return 'Google Inc. (NVIDIA)';
                    if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060, OpenGL 4.5)';
                    return getParameter2.call(this, param);
                };
            }
        """)

    async def get_page(self) -> Page:
        """Get current page or launch browser."""
        if not self.is_running:
            return await self.launch()
        return self._page

    async def new_page(self) -> Page:
        """Create a new page/tab."""
        if not self.is_running:
            await self.launch()

        if self._using_cdp and self._context:
            page = await self._context.new_page()
        elif self._context:
            page = await self._context.new_page()
        else:
            page = await self._page if self._page else await self.launch()

        return page

    async def close(self):
        """Close browser or disconnect from CDP."""
        self._is_running = False
        self._page = None

        if self._using_cdp:
            # CDP mode: only disconnect, don't close user's browser
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.debug("CDP disconnect error: %s", e)
                self._browser = None
            logger.info("已断开与用户 Chrome 的连接")
        else:
            # Own browser: close everything
            if self._context:
                try:
                    await self._context.close()
                except Exception as e:
                    logger.debug("Error closing browser context: %s", e)
                self._context = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.debug("Error stopping playwright: %s", e)
            self._playwright = None


# Singleton instance
browser_manager = BrowserManager()
