# -*- coding: utf-8 -*-
"""Authentication & Session management for ZJNU CAS SSO.

Handles:
- CAS SSO login with encrypted password (AES via ez.js)
- Cookie persistence (JSON)
- Token extraction & persistence (JSON)
- Session validation & auto re-login
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import execjs
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("auth")

DIR = Path(__file__).parent.resolve()

# ── CryptoJS (from ez.js) ──
_EZJS = execjs.compile((DIR / "ez.js").read_text("utf-8"))

# ── URLs ──
CAS_URL = "http://authserver.zjnu.edu.cn:80/authserver/login"
CAS_SVC = "https://tycg.zjnu.edu.cn/api/cas_auth/auth"
BASE_URL = "https://tycg.zjnu.edu.cn"
LOGIN_URL = f"{CAS_URL}?service={requests.utils.quote(CAS_SVC, safe='')}"

# ── Persistence paths ──
COOKIE_FILE = DIR / "cookies.json"
TOKEN_FILE = DIR / "token.json"

# ── Default headers ──
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8",
}


class Session:
    """Manages authentication state: cookies, token, and HTTP session.

    Persists cookies to cookies.json and token to token.json for
    fast recovery across script restarts.
    """

    def __init__(self):
        self.http = requests.Session()
        self.http.headers.update(DEFAULT_HEADERS)
        self.token = None
        self._username = None

    # ── Persistence ──

    def _save_cookies(self):
        """Save all session cookies to JSON file."""
        cookies = []
        for c in self.http.cookies:
            cookies.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
            })
        COOKIE_FILE.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_cookies(self):
        """Load cookies from JSON file into session. Returns True if any loaded."""
        if not COOKIE_FILE.exists():
            return False
        try:
            cookies = json.loads(COOKIE_FILE.read_text("utf-8"))
            for c in cookies:
                self.http.cookies.set(
                    c["name"], c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )
            return len(cookies) > 0
        except (json.JSONDecodeError, KeyError):
            return False

    def _save_token(self):
        """Save token with timestamp to JSON file."""
        if not self.token:
            return
        TOKEN_FILE.write_text(
            json.dumps({
                "token": self.token,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_token(self):
        """Load token from JSON file. Returns token string or None."""
        if not TOKEN_FILE.exists():
            return None
        try:
            data = json.loads(TOKEN_FILE.read_text("utf-8"))
            token = data.get("token", "")
            if token:
                log.info("Token loaded (saved at %s)", data.get("saved_at", "?"))
                return token
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def save(self):
        """Persist both cookies and token."""
        self._save_cookies()
        if self.token:
            self._save_token()

    def load(self):
        """Try to restore session from disk. Returns True if both cookie and token loaded."""
        if not self._load_cookies():
            return False
        self.token = self._load_token()
        if self.token:
            log.info("Session restored from disk (cookie + token)")
        else:
            log.info("Cookies restored, but no token found")
        return bool(self.token)

    # ── Validation ──

    @property
    def tok(self):
        """Shortcut for token existence check."""
        return bool(self.token)

    def is_logged_in(self):
        """Check if the current session is still authenticated."""
        try:
            resp = self.http.get(BASE_URL, allow_redirects=True, timeout=10)
            page = resp.text
            if "统一身份认证" in page or "登录" in page:
                return False
            return True
        except Exception as e:
            log.warning("Login check failed: %s", e)
            return False

    # ── CAS Login ──

    def login(self, username, password):
        """Perform CAS SSO login.

        Args:
            username: Student ID
            password: Plaintext password (will be AES-encrypted)

        Returns:
            True on success

        Raises:
            RuntimeError: If login fails
        """
        self._username = username
        log.info("Logging in as %s ...", username)

        # Step 1: Visit SSO login page to get execution token & salt
        resp = self.http.get(LOGIN_URL, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract hidden form fields
        execution_el = soup.find("input", {"name": "execution"})
        salt_el = soup.find("input", {"id": "pwdEncryptSalt"})

        if not execution_el or not salt_el:
            raise RuntimeError(
                "Failed to parse login page. "
                "The CAS page structure may have changed."
            )

        execution = execution_el.get("value", "")
        pwd_salt = salt_el.get("value", "")

        if not execution or not pwd_salt:
            raise RuntimeError("Missing execution token or password salt.")

        # Step 2: AES-encrypt password using ez.js CryptoJS
        encrypted_pwd = _EZJS.call("encryptPassword", password, pwd_salt)
        log.debug("Encrypted password: %s...", encrypted_pwd[:20])

        # Step 3: POST login
        login_data = {
            "username": username,
            "password": encrypted_pwd,
            "captcha": "",
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "execution": execution,
        }

        login_headers = {
            **DEFAULT_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "http://authserver.zjnu.edu.cn",
            "Referer": LOGIN_URL,
        }

        login_resp = self.http.post(LOGIN_URL, data=login_data, headers=login_headers, allow_redirects=True)

        # Step 4: Verify
        if not self.is_logged_in():
            log.error("Login failed. Response snippet: %s", login_resp.text[:300])
            raise RuntimeError(
                "Login failed. Check credentials or CAS page structure."
            )

        log.info("CAS login successful!")

        # Step 5: Extract & save token
        self._extract_and_save_token()

        # Step 6: Save session
        self.save()
        log.info("Session saved (cookies + token)")

        return True

    def _extract_and_save_token(self):
        """Visit venue page and extract API token from redirect URL."""
        venue_url = f"{BASE_URL}/venue"
        try:
            resp = self.http.get(venue_url, allow_redirects=True, timeout=10)

            # Try extracting from URL query string
            token_match = re.search(r"token=([^&]+)", resp.url)
            if token_match:
                self.token = token_match.group(1)
                log.info("Token extracted from URL: %s...", self.token[:20])
                self._save_token()
                return

            # Try extracting from page JavaScript/JSON
            token_match = re.search(r'"token"\s*:\s*"([^"]+)"', resp.text)
            if token_match:
                self.token = token_match.group(1)
                log.info("Token extracted from response body: %s...", self.token[:20])
                self._save_token()
                return

            log.warning("Token not found in venue page (URL: %s)", resp.url[:100])

        except Exception as e:
            log.warning("Failed to extract token: %s", e)

    def ensure_token(self):
        """Ensure we have a valid token. Re-extract if missing."""
        if self.token:
            return True

        if not self.is_logged_in():
            log.warning("Session expired, cannot extract token")
            return False

        self._extract_and_save_token()
        return bool(self.token)

    # ── HTTP Helpers ──

    def get(self, path, **kwargs):
        """GET request with base URL prefix and Authorization header."""
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = self.token
        resp = self.http.get(url, headers=headers, allow_redirects=True, timeout=10, **kwargs)
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def post(self, path, data=None, json_data=None, **kwargs):
        """POST request with base URL, Authorization header, and JSON body support."""
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = self.token
        if json_data is not None:
            headers["Content-Type"] = "application/json"
            resp = self.http.post(
                url, json=json_data, headers=headers,
                allow_redirects=True, timeout=10, **kwargs
            )
        else:
            resp = self.http.post(
                url, data=data, headers=headers,
                allow_redirects=True, timeout=10, **kwargs
            )
        try:
            return resp.json()
        except ValueError:
            return resp.text
