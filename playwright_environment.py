from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

from cer_architecture import AgentAction

try:
    from playwright.sync_api import (
        Error as PlaywrightError,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except ImportError:
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


class PlaywrightEnvironment:
    """Execute CER actions against a real browser using Playwright."""

    def __init__(
        self,
        headless: bool = False,
        slow_mo_ms: int = 80,
        browser_channel: str = "chrome",
        default_timeout_ms: int = 10000,
        keep_open: bool = True,
    ) -> None:
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
        self.browser_channel = browser_channel
        self.default_timeout_ms = default_timeout_ms
        self.keep_open = keep_open

        self._playwright: Optional[Any] = None
        self._browser: Optional[Any] = None
        self._context: Optional[Any] = None
        self._page: Optional[Any] = None
        self._id_to_selector: Dict[int, str] = {}
        self._last_observation_text: str = ""

    def execute_action(self, action: AgentAction) -> Dict[str, Any]:
        """Parse one action and execute it in browser."""

        parsed = self._parse_action(action)
        action_name = parsed["action"]
        resolved_target = self._resolve_target(parsed["target"])
        parsed["target"] = resolved_target

        try:
            page = self._ensure_page()
            parsed["target"] = self._prefer_baidu_new_home_controls(page, parsed["target"])

            if action_name in {"type", "fill"}:
                parsed["target"] = self._ensure_typing_target(page, parsed["target"])

            if action_name == "press" and (parsed["value"] or "").strip().lower() == "enter":
                parsed["target"] = self._ensure_enter_target(page, parsed["target"])

            if action_name in {"", "noop", "think"}:
                return {"done": False, "observation": "No browser action executed."}

            if action_name in {"goto", "navigate"}:
                url = parsed["url"] or parsed["target"] or parsed["value"]
                if not url:
                    return {"done": False, "error": "goto action requires <url> or <target>."}
                normalized_url = self._normalize_url(url)
                page.goto(normalized_url, wait_until="domcontentloaded")
                return {"done": False, "observation": f"Navigated to: {normalized_url}"}

            if action_name == "fill":
                if not parsed["target"]:
                    return {"done": False, "error": "fill action requires <target>."}
                if parsed["value"] == "":
                    return {"done": False, "error": "fill action requires <value>."}
                filled = self._fill_with_fallback(page, parsed["target"], parsed["value"])
                if not filled:
                    return {
                        "done": False,
                        "error": f"Unable to fill target: {parsed['target']}",
                    }
                return {
                    "done": False,
                    "observation": f"Filled {parsed['target']} with: {parsed['value']}",
                }

            if action_name == "type":
                if not parsed["target"]:
                    return {"done": False, "error": "type action requires <target>."}
                if parsed["value"] == "":
                    return {"done": False, "error": "type action requires <value>."}
                typed = self._type_with_fallback(page, parsed["target"], parsed["value"])
                if not typed:
                    return {
                        "done": False,
                        "error": f"Unable to type into target: {parsed['target']}",
                    }
                return {
                    "done": False,
                    "observation": f"Typed into {parsed['target']}: {parsed['value']}",
                }

            if action_name == "click":
                if not parsed["target"]:
                    return {"done": False, "error": "click action requires <target>."}
                click_selector = self._visible_selector(parsed["target"])
                page.click(click_selector)
                return {"done": False, "observation": f"Clicked: {parsed['target']}"}

            if action_name == "press":
                key = parsed["value"] or "Enter"
                if parsed["target"]:
                    page.press(parsed["target"], key)
                    return {"done": False, "observation": f"Pressed {key} on {parsed['target']}"}
                page.keyboard.press(key)
                return {"done": False, "observation": f"Pressed {key}"}

            if action_name == "wait":
                seconds = self._parse_wait_seconds(parsed["value"])
                time.sleep(seconds)
                return {"done": False, "observation": f"Waited {seconds:.1f} seconds."}

            if action_name in {"finish", "done", "complete", "completed"}:
                return {
                    "done": True,
                    "final_answer": parsed["value"] or parsed["target"] or "Task finished.",
                }

            return {"done": False, "error": f"Unsupported action: {action_name}"}
        except PlaywrightTimeoutError as exc:
            return {"done": False, "error": f"playwright_timeout: {exc}"}
        except PlaywrightError as exc:
            return {"done": False, "error": f"playwright_error: {exc}"}
        except Exception as exc:
            return {"done": False, "error": f"browser_action_failed: {exc}"}

    def get_observation(self, max_items: int = 80) -> Dict[str, Any]:
        """Return current page observation as compact text list for LLMs."""

        try:
            page = self._ensure_page()

            extracted = page.evaluate(
                """
                (args) => {
                  const maxItems = Number(args.maxItems) || 80;
                  const selector = [
                    'a',
                    'button',
                    'input',
                    'textarea',
                    'select',
                    '[role="button"]',
                    '[onclick]'
                  ].join(',');

                                    const candidates = Array.from(document.querySelectorAll(selector));
                                    const visible = (el) => {
                                        const style = window.getComputedStyle(el);
                                        const rect = el.getBoundingClientRect();
                                        const formControlTags = ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'];
                                        const isActionableFormControl =
                                            formControlTags.includes(el.tagName) &&
                                            style.visibility !== 'hidden' &&
                                            style.display !== 'none' &&
                                            String(el.getAttribute('type') || '').toLowerCase() !== 'hidden';

                                        if (isActionableFormControl) {
                                            return true;
                                        }

                                        return (
                                            style.visibility !== 'hidden' &&
                                            style.display !== 'none' &&
                                            rect.width > 2 &&
                                            rect.height > 2 &&
                                            rect.bottom >= 0 &&
                                            rect.right >= 0
                                        );
                                    };

                                    const cssEscape = (value) => {
                                        if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
                                        return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');
                                    };

                                    const quoteAttr = (value) => String(value).replace(/"/g, '\\"');

                                    const attrSelector = (tag, attr, value) => `${tag}[${attr}="${quoteAttr(value)}"]`;

                                    const isUnique = (selectorText) => {
                                        try {
                                            return document.querySelectorAll(selectorText).length === 1;
                                        } catch (_) {
                                            return false;
                                        }
                                    };

                                    const buildPathSelector = (el) => {
                                        const segments = [];
                                        let node = el;
                                        let depth = 0;
                                        while (node && node.nodeType === 1 && depth < 5) {
                                            let part = node.tagName.toLowerCase();
                                            if (node.id) {
                                                part = `#${cssEscape(node.id)}`;
                                                segments.unshift(part);
                                                break;
                                            }

                                            const parent = node.parentElement;
                                            if (parent) {
                                                const sameTagSiblings = Array.from(parent.children).filter(
                                                    (child) => child.tagName === node.tagName
                                                );
                                                if (sameTagSiblings.length > 1) {
                                                    const index = sameTagSiblings.indexOf(node) + 1;
                                                    part += `:nth-of-type(${index})`;
                                                }
                                            }

                                            segments.unshift(part);
                                            node = parent;
                                            depth += 1;
                                        }
                                        return segments.join(' > ');
                                    };

                                    const buildSelector = (el) => {
                                        const tag = el.tagName.toLowerCase();
                                        if (el.id) return `#${cssEscape(el.id)}`;

                                        const candidates = [];
                                        const name = el.getAttribute('name');
                                        const ariaLabel = el.getAttribute('aria-label');
                                        const placeholder = el.getAttribute('placeholder');
                                        const title = el.getAttribute('title');
                                        const href = tag === 'a' ? el.getAttribute('href') : null;

                                        if (name) candidates.push(attrSelector(tag, 'name', name));
                                        if (ariaLabel) candidates.push(attrSelector(tag, 'aria-label', ariaLabel));
                                        if (placeholder) candidates.push(attrSelector(tag, 'placeholder', placeholder));
                                        if (title) candidates.push(attrSelector(tag, 'title', title));
                                        if (href && href.length <= 220) candidates.push(attrSelector(tag, 'href', href));

                                        for (const candidateSelector of candidates) {
                                            if (isUnique(candidateSelector)) {
                                                return candidateSelector;
                                            }
                                        }

                                        const pathSelector = buildPathSelector(el);
                                        if (pathSelector && isUnique(pathSelector)) {
                                            return pathSelector;
                                        }
                                        return pathSelector || tag;
                                    };

                                    const semanticRole = (el) => {
                                        const explicitRole = el.getAttribute('role');
                                        if (explicitRole) return explicitRole.toLowerCase();
                                        const tag = el.tagName.toLowerCase();
                                        if (tag === 'input') {
                                            const inputType = String(el.getAttribute('type') || 'text').toLowerCase();
                                            return `input:${inputType}`;
                                        }
                                        return tag;
                                    };

                  const label = (el) => {
                    const parts = [
                      el.innerText,
                      el.value,
                      el.getAttribute('aria-label'),
                      el.getAttribute('placeholder'),
                      el.getAttribute('title')
                    ].filter(Boolean);
                    const text = parts.length ? String(parts[0]).trim() : '';
                    return text.replace(/\\s+/g, ' ').slice(0, 120);
                  };

                                    const hasBaiduChatInput = Boolean(document.querySelector('#chat-textarea'));
                                    const hasBaiduChatSubmit = Boolean(document.querySelector('#chat-submit-button'));

                                    const output = [];
                  for (const el of candidates) {
                    if (!visible(el)) continue;
                    if (output.length >= maxItems) break;

                                        if (hasBaiduChatInput && hasBaiduChatSubmit) {
                                            const elementId = String(el.id || '').toLowerCase();
                                            if (elementId === 'kw' || elementId === 'su') {
                                                continue;
                                            }
                                        }

                                        output.push({
                                            role: semanticRole(el),
                                            text: label(el),
                                            selector: buildSelector(el)
                                        });
                  }
                                    const priority = (item) => {
                                        const role = String(item.role || '').toLowerCase();
                                        if (role.startsWith('textarea')) return 0;
                                        if (role.startsWith('input:text')) return 1;
                                        if (role.startsWith('input:search')) return 2;
                                        if (role.startsWith('input')) return 3;
                                        if (role.includes('button') || role === 'button') return 4;
                                        if (role.startsWith('select')) return 5;
                                        return 9;
                                    };

                                    output.sort((a, b) => {
                                        const pa = priority(a);
                                        const pb = priority(b);
                                        if (pa !== pb) return pa - pb;
                                        return String(a.text || '').localeCompare(String(b.text || ''));
                                    });
                                    return output;
                }
                """,
                {"maxItems": max_items},
            )

            elements_raw = extracted if isinstance(extracted, list) else []
            self._id_to_selector = {}
            lines: list[str] = []
            elements: list[Dict[str, Any]] = []

            for index, item in enumerate(elements_raw, start=1):
                if not isinstance(item, dict):
                    continue

                role = str(item.get("role", "element")).strip() or "element"
                text = str(item.get("text", "")).strip()
                selector = str(item.get("selector", "")).strip()

                if not selector:
                    continue

                self._id_to_selector[index] = selector
                label_text = text if text else "<no-text>"
                lines.append(f"[{index}] {role} '{label_text}' selector='{selector}'")
                elements.append(
                    {
                        "id": index,
                        "role": role,
                        "text": label_text,
                        "selector": selector,
                    }
                )

            current_url = str(page.url)
            page_title = str(page.title())
            observation_text = "\n".join(lines)
            if not observation_text:
                observation_text = "<no-visible-interactive-elements>"

            self._last_observation_text = observation_text
            return {
                "url": current_url,
                "title": page_title,
                "count": len(elements),
                "elements": elements,
                "observation_text": observation_text,
            }
        except Exception as exc:
            return {
                "url": "",
                "title": "",
                "count": 0,
                "elements": [],
                "observation_text": "<observation-unavailable>",
                "error": f"observation_failed: {exc}",
            }

    def close(self) -> None:
        """Release Playwright resources."""

        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        finally:
            self._context = None

        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None
            self._page = None

    def _ensure_page(self) -> Any:
        if self._page is not None:
            return self._page

        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright and python -m playwright install chrome"
            )

        self._playwright = sync_playwright().start()

        try:
            self._browser = self._playwright.chromium.launch(
                channel=self.browser_channel,
                headless=self.headless,
                slow_mo=self.slow_mo_ms,
            )
        except Exception:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo_ms,
            )

        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.default_timeout_ms)
        return self._page

    @staticmethod
    def _extract_tag(raw: str, tag: str) -> str:
        match = re.search(fr"<{tag}>\s*(.*?)\s*</{tag}>", raw, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _parse_action(self, action: AgentAction) -> Dict[str, str]:
        raw = str(action.get("raw", ""))
        action_name = str(action.get("type", "")).strip().lower()

        action_from_xml = self._extract_tag(raw, "action").lower()
        if action_from_xml:
            action_name = action_from_xml

        target = str(action.get("target", "")).strip() or self._extract_tag(raw, "target")
        value = str(action.get("value", "")).strip() or self._extract_tag(raw, "value")
        url = self._extract_tag(raw, "url")

        return {
            "action": action_name,
            "target": target,
            "value": value,
            "url": url,
        }

    def _resolve_target(self, target: str) -> str:
        """Resolve observation ID target format like [12] to real selector."""

        cleaned = target.strip()
        if not cleaned:
            return cleaned

        observation_id = self._target_to_observation_id(cleaned)
        if observation_id is None:
            return cleaned

        return self._id_to_selector.get(observation_id, cleaned)

    @staticmethod
    def _target_to_observation_id(target: str) -> Optional[int]:
        """Parse an observation target string into integer id if possible."""

        bracket_match = re.match(r"^\[(\d+)\]$", target)
        if bracket_match:
            return int(bracket_match.group(1))

        prefix_match = re.match(r"^(?:id\s*[:=]\s*)(\d+)$", target, flags=re.IGNORECASE)
        if prefix_match:
            return int(prefix_match.group(1))

        plain_digits_match = re.match(r"^(\d+)$", target)
        if plain_digits_match:
            return int(plain_digits_match.group(1))

        return None

    @staticmethod
    def _prefer_baidu_new_home_controls(page: Any, target: str) -> str:
        """Map legacy Baidu selectors to new visible controls when available."""

        cleaned = target.strip()
        if cleaned not in {"#kw", "#su"}:
            return cleaned

        try:
            has_chat_input = page.query_selector("#chat-textarea") is not None
            has_chat_submit = page.query_selector("#chat-submit-button") is not None
        except Exception:
            return cleaned

        if not (has_chat_input and has_chat_submit):
            return cleaned

        if cleaned == "#kw":
            return "#chat-textarea"
        if cleaned == "#su":
            return "#chat-submit-button"
        return cleaned

    @staticmethod
    def _ensure_typing_target(page: Any, target: str) -> str:
        """Ensure type/fill actions operate on an editable text control."""

        cleaned = target.strip()
        if PlaywrightEnvironment._is_text_entry_selector(page, cleaned):
            return cleaned

        preferred = PlaywrightEnvironment._pick_preferred_text_target(page)
        return preferred or cleaned

    @staticmethod
    def _ensure_enter_target(page: Any, target: str) -> str:
        """Ensure Enter key is applied to an editable text control when possible."""

        cleaned = target.strip()
        if PlaywrightEnvironment._is_text_entry_selector(page, cleaned):
            return cleaned

        preferred = PlaywrightEnvironment._pick_preferred_text_target(page)
        return preferred or cleaned

    @staticmethod
    def _pick_preferred_text_target(page: Any) -> str:
        """Pick a robust text-entry selector for current page."""

        candidates = [
            "#chat-textarea",
            "textarea",
            "input[type='search']",
            "input[type='text']",
            "input:not([type])",
            "#kw",
        ]
        for selector in candidates:
            try:
                element = page.query_selector(selector)
                if element is not None:
                    return selector
            except Exception:
                continue
        return ""

    @staticmethod
    def _is_text_entry_selector(page: Any, selector: str) -> bool:
        """Check whether a selector currently points to an editable text control."""

        cleaned = selector.strip()
        if not cleaned:
            return False

        try:
            element = page.query_selector(cleaned)
            if element is None:
                return False

            tag_name = str(element.evaluate("el => el.tagName.toLowerCase()"))
            if tag_name == "textarea":
                return True

            if tag_name == "input":
                input_type = str(element.evaluate("el => (el.type || 'text').toLowerCase()"))
                non_text_types = {"hidden", "submit", "button", "checkbox", "radio", "file", "image", "reset"}
                return input_type not in non_text_types

            return False
        except Exception:
            return False

    @staticmethod
    def _normalize_url(url: str) -> str:
        cleaned = url.strip()
        if not cleaned:
            return cleaned
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned):
            return cleaned
        return f"https://{cleaned}"

    @staticmethod
    def _parse_wait_seconds(value: str) -> float:
        try:
            parsed = float(value.strip() or "1")
        except ValueError:
            parsed = 1.0
        return max(0.1, min(parsed, 30.0))

    def _fill_with_fallback(self, page: Any, target: str, value: str) -> bool:
        """Fill input robustly when duplicated/hidden nodes exist."""

        selectors = [self._visible_selector(target), target]
        for selector in selectors:
            try:
                page.wait_for_selector(selector, state="visible", timeout=3500)
                page.fill(selector, value, timeout=3500)
                return True
            except Exception:
                continue

        try:
            # Last fallback: set value by JS and dispatch input/change events.
            updated = page.evaluate(
                """
                (args) => {
                  const el = document.querySelector(args.selector);
                  if (!el) return false;
                  el.value = args.value;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
                """,
                {"selector": target, "value": value},
            )
            return bool(updated)
        except Exception:
            return False

    def _type_with_fallback(self, page: Any, target: str, value: str) -> bool:
        """Type text with delay for visible effect and robust element fallback."""

        selectors = [self._visible_selector(target), target]
        for selector in selectors:
            try:
                page.wait_for_selector(selector, state="visible", timeout=3500)
                page.fill(selector, "", timeout=3500)
                page.type(selector, value, delay=120)
                return True
            except Exception:
                continue

        try:
            # Last fallback: emulate typing via JS with incremental updates.
            updated = page.evaluate(
                """
                async (args) => {
                  const el = document.querySelector(args.selector);
                  if (!el) return false;
                  el.value = '';
                  for (const ch of args.value) {
                    el.value += ch;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    await new Promise((resolve) => setTimeout(resolve, 80));
                  }
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
                """,
                {"selector": target, "value": value},
            )
            return bool(updated)
        except Exception:
            return False

    @staticmethod
    def _visible_selector(selector: str) -> str:
        """Return a selector variant that prefers visible elements when possible."""

        cleaned = selector.strip()
        if not cleaned:
            return cleaned
        if ":visible" in cleaned:
            return cleaned
        if cleaned.startswith("//") or cleaned.startswith("("):
            return cleaned
        return f"{cleaned}:visible"
