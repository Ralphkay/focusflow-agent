# categorization.py
"""
Categorization module for determining if an application/website activity is
Productive, Neutral, or Unproductive.
"""

import logging
import re
from urllib.parse import urlparse

from config import CONFIG

logger = logging.getLogger(__name__)


def categorize_activity(app_name: str, window_title: str) -> str:
    """
    Determines the category (Productive, Neutral, Unproductive) for an activity
    based on the application name and window title.
    
    Args:
        app_name: The executable name (e.g., 'chrome.exe', 'excel.exe')
        window_title: The window title or extracted domain
        
    Returns:
        One of: 'Productive', 'Neutral', 'Unproductive'
    """
    if not app_name:
        return "Neutral"
    
    app_name_lower = app_name.lower().strip()
    window_title_lower = (window_title or "").lower().strip()
    
    # Get the app_config dictionary from CONFIG
    app_config = CONFIG.get("app_config", {})
    
    # Step 1: Check if the app is a browser - if so, categorize by website
    browser_names = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'iexplore.exe', 
                     'brave.exe', 'opera.exe', 'vivaldi.exe', 'safari.exe',
                     'chromium.exe', 'librewolf.exe', 'waterfox.exe', 'arc.exe',
                     'microsoftedge.exe']
    
    if app_name_lower in browser_names:
        # For browsers, categorize based on the website/domain in the window title
        website_category = categorize_website(window_title_lower)
        if website_category:
            return website_category
        # If no website match, browsers are considered Neutral by default
        return "Neutral"
    
    # Step 2: Direct lookup in app_config (try multiple variations)
    # Try exact match first
    if app_name_lower in app_config:
        return app_config[app_name_lower].get("category", "Neutral")
    
    # Try without .exe extension
    app_name_no_ext = app_name_lower.replace('.exe', '')
    if app_name_no_ext in app_config:
        return app_config[app_name_no_ext].get("category", "Neutral")
    
    # Try with .exe extension if not present
    if not app_name_lower.endswith('.exe'):
        app_name_with_ext = f"{app_name_lower}.exe"
        if app_name_with_ext in app_config:
            return app_config[app_name_with_ext].get("category", "Neutral")
    
    # Step 3: Pattern-based matching for common app name patterns
    category = match_app_patterns(app_name_lower, window_title_lower)
    if category:
        return category
    
    # Step 4: Default to Neutral for unknown apps
    logger.debug(f"No category found for app '{app_name}', defaulting to Neutral")
    return "Neutral"


def categorize_website(window_title_or_domain: str) -> str:
    """
    Categorizes a website based on the window title or domain.
    
    Args:
        window_title_or_domain: The browser window title or extracted domain
        
    Returns:
        Category string or None if no match found
    """
    if not window_title_or_domain:
        return None
    
    title_lower = window_title_or_domain.lower()
    
    # Get website lists from CONFIG
    productive_websites = CONFIG.get("productive_websites", [])
    unproductive_websites = CONFIG.get("unproductive_websites", [])
    
    # Extract potential domain from the title
    domain = extract_domain_from_title(title_lower)
    
    # Check against productive websites
    for site in productive_websites:
        site_lower = site.lower()
        if site_lower in title_lower or site_lower in domain:
            return "Productive"
        # Also check if the domain matches
        if domain and (domain.endswith(site_lower) or site_lower.endswith(domain)):
            return "Productive"
    
    # Check against unproductive websites
    for site in unproductive_websites:
        site_lower = site.lower()
        if site_lower in title_lower or site_lower in domain:
            return "Unproductive"
        if domain and (domain.endswith(site_lower) or site_lower.endswith(domain)):
            return "Unproductive"
    
    # Additional pattern matching for common unproductive sites
    unproductive_patterns = [
        r'facebook\.com', r'instagram\.com', r'twitter\.com', r'x\.com',
        r'tiktok\.com', r'snapchat\.com', r'reddit\.com', r'pinterest\.com',
        r'youtube\.com/watch', r'netflix\.com', r'twitch\.tv',
        r'spotify\.com', r'discord\.com', r'telegram\.', r'whatsapp\.',
        r'amazon\.com/gp', r'ebay\.com', r'aliexpress\.com',
        r'bet365', r'draftkings', r'fanduel', r'pokerstars',
        r'9gag\.com', r'buzzfeed\.com', r'imgur\.com',
        r'tinder\.com', r'bumble\.com', r'match\.com',
    ]
    
    for pattern in unproductive_patterns:
        if re.search(pattern, title_lower):
            return "Unproductive"
    
    # Additional pattern matching for common productive sites
    productive_patterns = [
        r'github\.com', r'gitlab\.com', r'bitbucket\.org',
        r'stackoverflow\.com', r'docs\.google\.com', r'drive\.google\.com',
        r'sheets\.google\.com', r'slides\.google\.com',
        r'outlook\.', r'mail\.google\.com', r'teams\.microsoft\.com',
        r'sharepoint\.com', r'onedrive\.live\.com', r'office\.com',
        r'jira\.', r'confluence\.', r'trello\.com', r'asana\.com',
        r'salesforce\.com', r'servicenow\.com', r'zendesk\.com',
        r'aws\.amazon\.com', r'console\.aws', r'portal\.azure\.com',
        r'cloud\.google\.com', r'firebase\.google\.com',
        r'learn\.microsoft\.com', r'developer\.mozilla\.org',
        r'coursera\.org', r'udemy\.com', r'linkedin\.com/learning',
        r'chatgpt\.com', r'openai\.com', r'claude\.ai', r'anthropic\.com',
        r'perplexity\.ai', r'huggingface\.co',
    ]
    
    for pattern in productive_patterns:
        if re.search(pattern, title_lower):
            return "Productive"
    
    return None


def extract_domain_from_title(title: str) -> str:
    """
    Attempts to extract a domain name from a browser window title.
    
    Args:
        title: The browser window title
        
    Returns:
        Extracted domain or empty string
    """
    if not title:
        return ""
    
    # Try to find URL pattern
    url_match = re.search(r'https?://(?:www\.)?([a-z0-9\.-]+\.[a-z]{2,})', title)
    if url_match:
        return url_match.group(1)
    
    # Try to extract domain from common title patterns like "Page Title - domain.com"
    domain_match = re.search(r'[\|\-]\s*(?:www\.)?([a-z0-9\.-]+\.[a-z]{2,})\s*$', title)
    if domain_match:
        return domain_match.group(1)
    
    # Look for any domain-like pattern
    simple_match = re.search(r'([a-z0-9\-]+\.[a-z]{2,})', title)
    if simple_match:
        return simple_match.group(1)
    
    return ""


def match_app_patterns(app_name: str, window_title: str) -> str:
    """
    Matches application names against known patterns to determine category.
    This handles apps that might not be in the config but follow recognizable patterns.
    
    Args:
        app_name: Lowercase application name
        window_title: Lowercase window title
        
    Returns:
        Category string or None if no pattern matches
    """
    # Productive patterns - development, office, business tools
    productive_patterns = [
        # IDEs and editors
        r'code\.exe', r'vscode', r'visual studio', r'pycharm', r'intellij',
        r'eclipse', r'netbeans', r'sublime', r'notepad\+\+', r'vim', r'emacs',
        r'webstorm', r'phpstorm', r'rider', r'goland', r'clion', r'datagrip',
        r'android studio', r'xcode', r'atom',
        # Office apps
        r'winword', r'excel', r'powerpnt', r'outlook', r'onenote', r'msaccess',
        r'visio', r'project', r'publisher', r'teams',
        # Database tools
        r'ssms', r'mysql', r'postgres', r'pgadmin', r'dbeaver', r'datagrip',
        r'sqldeveloper', r'mongodb', r'robo3t', r'studio3t',
        # DevOps & Cloud
        r'docker', r'kubectl', r'terraform', r'ansible', r'vagrant',
        r'azure', r'aws', r'gcloud',
        # Communication (work)
        r'slack', r'zoom', r'webex', r'gotomeeting', r'msteams',
        # Version control
        r'git', r'sourcetree', r'gitkraken', r'tortoise',
        # API & Testing
        r'postman', r'insomnia', r'soapui', r'jmeter',
        # Terminals
        r'powershell', r'cmd\.exe', r'terminal', r'mintty', r'putty', r'winscp',
        # BI & Analytics
        r'powerbi', r'pbidesktop', r'tableau', r'qlik', r'alteryx',
    ]
    
    for pattern in productive_patterns:
        if re.search(pattern, app_name) or re.search(pattern, window_title):
            return "Productive"
    
    # Unproductive patterns - games, entertainment, social
    unproductive_patterns = [
        # Games
        r'steam', r'epicgames', r'origin', r'battle\.net', r'uplay', r'ubisoft',
        r'riot', r'league', r'valorant', r'fortnite', r'minecraft',
        r'roblox', r'diablo', r'warcraft', r'overwatch', r'dota', r'csgo', r'cs2',
        r'gta', r'fifa', r'nba2k', r'madden', r'cod\.exe', r'callofduty',
        r'apex', r'pubg', r'destiny', r'halo', r'fallout', r'skyrim',
        r'witcher', r'cyberpunk', r'eldenring', r'darksouls',
        r'sims', r'simcity', r'civilization', r'stellaris', r'totalwar',
        r'game', r'gaming',
        # Social media
        r'discord', r'telegram', r'whatsapp', r'signal', r'viber',
        r'facebook', r'instagram', r'twitter', r'tiktok', r'snapchat',
        r'reddit', r'tumblr', r'pinterest',
        # Streaming entertainment
        r'netflix', r'hulu', r'disney\+', r'hbomax', r'primevideo',
        r'spotify', r'deezer', r'tidal', r'pandora', r'soundcloud',
        r'twitch', r'obs\.exe', r'streamlabs',
        # Dating
        r'tinder', r'bumble', r'hinge', r'match\.com', r'okcupid',
        # Emulators
        r'bluestacks', r'noxplayer', r'ldplayer', r'memu', r'gameloop',
        r'pcsx', r'dolphin', r'cemu', r'yuzu', r'ryujinx', r'retroarch',
    ]
    
    for pattern in unproductive_patterns:
        if re.search(pattern, app_name) or re.search(pattern, window_title):
            return "Unproductive"
    
    # Neutral patterns - system utilities, general tools
    neutral_patterns = [
        r'explorer\.exe', r'taskmgr', r'control\.exe', r'mmc\.exe',
        r'calc', r'calculator', r'notepad\.exe', r'paint', r'snip',
        r'vlc', r'mediaplayer', r'photos', r'camera',
        r'7z', r'winrar', r'winzip', r'peazip',
        r'antivirus', r'defender', r'malware', r'security',
        r'update', r'installer', r'setup',
        r'svchost', r'dllhost', r'conhost', r'runtime',
    ]
    
    for pattern in neutral_patterns:
        if re.search(pattern, app_name):
            return "Neutral"
    
    return None


def get_category_for_app(app_name: str) -> str:
    """
    Simple lookup for an application's category from the config.
    
    Args:
        app_name: The application executable name
        
    Returns:
        Category string (Productive, Neutral, or Unproductive)
    """
    if not app_name:
        return "Neutral"
    
    app_config = CONFIG.get("app_config", {})
    app_name_lower = app_name.lower().strip()
    
    # Direct lookup
    if app_name_lower in app_config:
        return app_config[app_name_lower].get("category", "Neutral")
    
    # Try without/with .exe
    if app_name_lower.endswith('.exe'):
        without_ext = app_name_lower[:-4]
        if without_ext in app_config:
            return app_config[without_ext].get("category", "Neutral")
    else:
        with_ext = f"{app_name_lower}.exe"
        if with_ext in app_config:
            return app_config[with_ext].get("category", "Neutral")
    
    return "Neutral"


def is_productive(app_name: str, window_title: str = "") -> bool:
    """Helper function to check if an activity is productive."""
    return categorize_activity(app_name, window_title) == "Productive"


def is_unproductive(app_name: str, window_title: str = "") -> bool:
    """Helper function to check if an activity is unproductive."""
    return categorize_activity(app_name, window_title) == "Unproductive"


def is_neutral(app_name: str, window_title: str = "") -> bool:
    """Helper function to check if an activity is neutral."""
    return categorize_activity(app_name, window_title) == "Neutral"
