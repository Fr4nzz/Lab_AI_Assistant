"""Browser manager for controlling the web browser using Playwright."""
import asyncio
import base64
from typing import List, Dict, Optional, Any
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext, Playwright

# Ruta absoluta del directorio del módulo
MODULE_DIR = Path(__file__).parent.absolute()


class BrowserManager:
    """Manages browser sessions and provides deterministic browser control."""
    
    # Actions the agent is NEVER allowed to perform
    FORBIDDEN_WORDS = ["guardar", "save", "eliminar", "delete", "borrar", "remove"]
    
    def __init__(self, user_data_dir: str = None):
        # Si no se especifica, usar ruta relativa al módulo
        if user_data_dir is None:
            self.user_data_dir = str(MODULE_DIR / "browser_data")
        else:
            # Convertir a ruta absoluta si es relativa
            path = Path(user_data_dir)
            if not path.is_absolute():
                self.user_data_dir = str(MODULE_DIR / user_data_dir)
            else:
                self.user_data_dir = user_data_dir
        
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._elements_cache: List[Dict] = []
    
    async def start(self, headless: bool = False, browser: str = "msedge"):
        """
        Start the browser with persistent context.

        Args:
            headless: Run browser without GUI
            browser: Browser to use - "msedge", "chrome", or "chromium"
        """
        print(f"[BrowserManager] Usando browser_data en: {self.user_data_dir}")
        self.playwright = await async_playwright().start()

        # Base args for all modes
        browser_args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--disable-restore-session-state",
            "--disable-restore-background-contents",
            "--hide-crash-restore-bubble",
            "--noerrdialogs",
        ]

        # Additional args for headless/Docker mode (no X11/GPU)
        if headless:
            browser_args.extend([
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ])

        # For chromium (Docker), don't specify channel
        channel = None if browser == "chromium" else browser

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=headless,
            channel=channel,  # None for bundled chromium, "msedge"/"chrome" for installed browsers
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
            args=browser_args,
            ignore_default_args=["--enable-automation"],  # Less intrusive automation
        )
        # Close any restored tabs and start fresh
        if len(self.context.pages) > 1:
            print(f"[BrowserManager] Closing {len(self.context.pages) - 1} restored tab(s)...")
            for page in self.context.pages[1:]:
                await page.close()
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
    
    async def stop(self):
        """Close the browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def ensure_page(self) -> Page:
        """
        Ensure we have a valid page. If the page was closed, open a new one.
        Returns the valid page.
        """
        try:
            # Check if page is still valid by trying a simple operation
            if self.page and not self.page.is_closed():
                # Try to get URL - this will fail if page is actually closed
                _ = self.page.url
                return self.page
        except Exception:
            pass

        # Page is invalid, need to create a new one
        print("[BrowserManager] Page was closed, opening new tab...")

        if self.context:
            # Try to use existing page from context
            if self.context.pages:
                self.page = self.context.pages[0]
                print(f"[BrowserManager] Using existing tab: {self.page.url}")
            else:
                # Create new page
                self.page = await self.context.new_page()
                print("[BrowserManager] Created new tab")
                # Navigate to orders by default
                await self.page.goto("https://laboratoriofranz.orion-labs.com/ordenes", timeout=30000)
                print("[BrowserManager] Navigated to orders page")
        else:
            raise RuntimeError("Browser context is not available")

        return self.page

    async def navigate(self, url: str, wait_for: str = "networkidle"):
        """Navigate to a URL and wait for the page to load."""
        await self.ensure_page()
        await self.page.goto(url, timeout=60000)
        await self.page.wait_for_load_state(wait_for, timeout=30000)
    
    async def get_state(self) -> Dict[str, Any]:
        """Extract current browser state for AI context."""
        elements = await self._extract_elements()
        self._elements_cache = elements
        
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "elements": elements,
            "scroll_position": await self.page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
        }
    
    async def _extract_elements(self) -> List[Dict]:
        """Extract all interactive elements with indices."""
        script = """
        () => {
            const elements = [];
            const selectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
            const nodes = document.querySelectorAll(selectors);
            
            nodes.forEach((node, index) => {
                const rect = node.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 && 
                    window.getComputedStyle(node).visibility !== 'hidden' &&
                    window.getComputedStyle(node).display !== 'none';
                
                if (!isVisible) return;
                
                const element = {
                    index: elements.length,
                    tag: node.tagName.toLowerCase(),
                    type: node.type || null,
                    text: (node.innerText || node.value || '').substring(0, 100).trim(),
                    placeholder: node.placeholder || null,
                    name: node.name || null,
                    id: node.id || null,
                    href: node.href || null,
                    class: node.className || null,
                    options: null
                };
                
                // For select elements, get options
                if (node.tagName === 'SELECT') {
                    element.options = Array.from(node.options).map(opt => ({
                        value: opt.value,
                        text: opt.text.trim()
                    }));
                }
                
                elements.push(element);
            });
            
            return elements;
        }
        """
        return await self.page.evaluate(script)
    
    async def get_page_content(self) -> str:
        """Get simplified text content of the page."""
        return await self.page.evaluate("""
            () => {
                return document.body.innerText.substring(0, 5000);
            }
        """)
    
    async def get_screenshot(self, full_page: bool = False) -> str:
        """Take a screenshot and return as base64."""
        screenshot_bytes = await self.page.screenshot(full_page=full_page)
        return base64.b64encode(screenshot_bytes).decode('utf-8')
    
    def is_action_forbidden(self, action: Dict) -> bool:
        """Check if an action involves forbidden operations."""
        # Check element text
        if "element_index" in action:
            idx = action["element_index"]
            if idx < len(self._elements_cache):
                element = self._elements_cache[idx]
                text = (element.get("text", "") or "").lower()
                for word in self.FORBIDDEN_WORDS:
                    if word in text:
                        return True
        
        # Check action text directly
        if "text" in action:
            text = action["text"].lower()
            for word in self.FORBIDDEN_WORDS:
                if word in text:
                    return True
        
        return False
    
    async def execute_action(self, action: Dict) -> Dict[str, Any]:
        """
        Execute a browser action.
        
        Supported actions:
        - navigate: {"action": "navigate", "url": "..."}
        - click: {"action": "click", "element_index": N}
        - type: {"action": "type", "element_index": N, "text": "..."}
        - select: {"action": "select", "element_index": N, "value": "..."}
        - scroll: {"action": "scroll", "direction": "down/up", "amount": 500}
        - wait: {"action": "wait", "seconds": N}
        """
        if self.is_action_forbidden(action):
            return {
                "success": False,
                "error": "Action forbidden: involves save/delete operations"
            }
        
        action_type = action.get("action")
        
        try:
            if action_type == "navigate":
                await self.navigate(action["url"])
                return {"success": True, "message": f"Navigated to {action['url']}"}
            
            elif action_type == "click":
                element = await self._get_element_by_index(action["element_index"])
                if element:
                    await element.click()
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                    return {"success": True, "message": f"Clicked element {action['element_index']}"}
                return {"success": False, "error": "Element not found"}
            
            elif action_type == "type":
                element = await self._get_element_by_index(action["element_index"])
                if element:
                    clear = action.get("clear", True)
                    if clear:
                        await element.click()
                        await self.page.keyboard.press("Control+a")
                    await element.type(action["text"], delay=20)
                    return {"success": True, "message": f"Typed text in element {action['element_index']}"}
                return {"success": False, "error": "Element not found"}
            
            elif action_type == "select":
                element = await self._get_element_by_index(action["element_index"])
                if element:
                    value = action.get("value")
                    label = action.get("label")
                    if label:
                        await element.select_option(label=label)
                    elif value:
                        await element.select_option(value=value)
                    return {"success": True, "message": f"Selected option in element {action['element_index']}"}
                return {"success": False, "error": "Element not found"}
            
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                amount = action.get("amount", 500)
                if direction == "down":
                    await self.page.evaluate(f"window.scrollBy(0, {amount})")
                else:
                    await self.page.evaluate(f"window.scrollBy(0, -{amount})")
                return {"success": True, "message": f"Scrolled {direction} by {amount}px"}
            
            elif action_type == "wait":
                seconds = action.get("seconds", 1)
                await asyncio.sleep(seconds)
                return {"success": True, "message": f"Waited {seconds} seconds"}
            
            elif action_type == "press_key":
                key = action.get("key", "Tab")
                await self.page.keyboard.press(key)
                return {"success": True, "message": f"Pressed {key}"}
            
            else:
                return {"success": False, "error": f"Unknown action type: {action_type}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_element_by_index(self, index: int):
        """Get element by its index in the elements cache."""
        if index >= len(self._elements_cache):
            return None
        
        element_info = self._elements_cache[index]
        
        # Build selector based on available info
        if element_info.get("id"):
            selector = f"#{element_info['id']}"
        elif element_info.get("name"):
            tag = element_info.get("tag", "*")
            selector = f"{tag}[name='{element_info['name']}']"
        else:
            # Fallback: use nth-of-type with tag
            script = f"""
            () => {{
                const selectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                const nodes = Array.from(document.querySelectorAll(selectors)).filter(node => {{
                    const rect = node.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }});
                return nodes[{index}] ? true : false;
            }}
            """
            exists = await self.page.evaluate(script)
            if exists:
                # Return element using JS
                return await self.page.evaluate_handle(f"""
                    () => {{
                        const selectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                        const nodes = Array.from(document.querySelectorAll(selectors)).filter(node => {{
                            const rect = node.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }});
                        return nodes[{index}];
                    }}
                """)
            return None
        
        try:
            return await self.page.query_selector(selector)
        except:
            return None
    
