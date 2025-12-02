# utils.py
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def sanitize_log(data: str) -> str:
    """Sanitize sensitive data before logging."""
    if not data:
        return ""
    # Use a generic regex to redact email addresses
    return re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED]', data)


def clean_incognito_markers(title: str) -> str:
    """
    Removes incognito/private browsing markers from window titles.
    This allows tracking of incognito browsing activity normally.
    """
    if not title:
        return title
    
    # Common incognito/private mode markers to remove
    incognito_patterns = [
        r'\s*[\-\|]\s*Incognito\s*$',           # Chrome: "Page - Incognito"
        r'\s*\(Incognito\)\s*',                  # Chrome: "(Incognito)"
        r'\s*[\-\|]\s*InPrivate\s*$',           # Edge: "Page - InPrivate"
        r'\s*\(InPrivate\)\s*',                  # Edge: "(InPrivate)"
        r'\s*[\-\|]\s*Private Browsing\s*$',    # Firefox: "Page - Private Browsing"
        r'\s*\(Private Browsing\)\s*',           # Firefox: "(Private Browsing)"
        r'\s*[\-\|]\s*Private\s*$',              # Safari/Opera: "Page - Private"
        r'\s*\(Private\)\s*',                    # Generic: "(Private)"
        r'^\[Private\]\s*',                      # Some browsers: "[Private] Page"
        r'^\[Incognito\]\s*',                    # Some browsers: "[Incognito] Page"
    ]
    
    cleaned_title = title
    for pattern in incognito_patterns:
        cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)
    
    return cleaned_title.strip()


def extract_domain_or_title(window_title: str, app_name: str) -> str:
    """
    Extracts a clean domain name from a browser window title.
    For non-browser applications, it returns the original window title.
    Handles incognito/private browsing windows by stripping markers.
    """
    if not isinstance(window_title, str) or not isinstance(app_name, str):
        return "N/A"

    # Clean incognito markers before processing
    window_title = clean_incognito_markers(window_title)
    
    window_title_lower = window_title.lower().strip()
    app_name_lower = app_name.lower().strip()

    # Define a list of known browser process names
    browser_names = ['chrome', 'firefox', 'msedge', 'iexplore', 'brave', 'safari', 'opera']
    if not any(browser in app_name_lower for browser in browser_names):
        # If it's not a browser, return the original window title
        return window_title

    # --- Stage 1: Specific Browser Title Patterns ---
    # This handles common title formats from major browsers.
    # Pattern 1: "Page Title - Domain Name" or "Page Title | Domain Name"
    match = re.search(r'[\|\-]\s*(?:www\.)?([a-z0-9\.-]+\.[a-z]{2,})(?:\s*|(?:\s*\[.*?\]|\s*\.\.\.)?)$',
                      window_title_lower)
    if match:
        domain = match.group(1).strip()
        if '.' in domain and domain not in ['localhost']:
            return domain

    # --- Stage 2: Generic URL-like Pattern from the entire title ---
    # This is a fallback for titles that might contain the full URL.
    match_url = re.search(r'https?://(?:www\.)?([a-z0-9\.-]+\.[a-z]{2,})', window_title_lower)
    if match_url:
        return match_url.group(1).strip()

    # --- Stage 3: Simple, less specific fallback for domains in the title ---
    # This is a last-resort for very minimal titles or non-standard formats.
    simple_match = re.search(r'([a-z0-9\-]+\.[a-z]{2,})', window_title_lower)
    if simple_match:
        domain = simple_match.group(1).strip()
        if '.' in domain and len(domain.split('.')[0]) > 2 and domain not in ['local.host', 'localhost']:
            return domain

    # If a domain could not be extracted from a browser title, fall back to the original window title.
    logger.debug(
        f"Could not extract a domain from browser title: '{window_title}' using all regex methods. Falling back to full title.")
    return window_title