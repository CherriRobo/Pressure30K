#Imports.
import os
import time
import aiohttp
from typing import Dict, List, Optional

#Helix.
HELIX = "https://api.twitch.tv/helix"

#Load env.
TWITCH_CLIENT = os.getenv("TWITCH_CLIENT")
TWITCH_SECRET = os.getenv("TWITCH_SECRET")

if not TWITCH_CLIENT or not TWITCH_SECRET:
    pass

#API helper.
class TWITCHAPI:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.token: Optional[str] = None
        self.token_expiry_ts: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session and not self.session.closed:
            return self.session
        self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _ensure_token(self):
        if self.token and time.time() < (self.token_expiry_ts - 60):
            return

        sess = await self._get_session()
        async with sess.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": TWITCH_CLIENT,
                "client_secret": TWITCH_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=20,
        ) as r:
            data = await r.json()
            self.token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            self.token_expiry_ts = time.time() + expires_in

    async def _headers(self) -> Dict[str, str]:
        await self._ensure_token()
        return {
            "Client-ID": TWITCH_CLIENT,
            "Authorization": f"Bearer {self.token}",
        }

    async def fetch_users(self, logins: List[str]) -> Dict[str, dict]:
        if not logins:
            return {}
        sess = await self._get_session()
        params = [("login", u) for u in logins]
        async with sess.get(f"{HELIX}/users", params=params, headers=await self._headers(), timeout=20) as r:
            data = await r.json()
            return {u["login"].lower(): u for u in data.get("data", [])}

    async def fetch_streams(self, logins: List[str]) -> List[dict]:
        if not logins:
            return []
        sess = await self._get_session()
        params = [("user_login", u) for u in logins]
        async with sess.get(f"{HELIX}/streams", params=params, headers=await self._headers(), timeout=20) as r:
            data = await r.json()
            return data.get("data", []) or []

    async def fetch_broadcaster_ids(self, logins: List[str]) -> Dict[str, str]:
        users = await self.fetch_users(logins)
        return {login: u.get("id") for login, u in users.items() if u.get("id")}

    async def fetch_clips(self, broadcaster_id: str, started_at_iso: str) -> List[dict]:
        if not broadcaster_id:
            return []
        sess = await self._get_session()
        params = {
            "broadcaster_id": broadcaster_id,
            "started_at": started_at_iso,
            "first": 20,
        }
        async with sess.get(f"{HELIX}/clips", params=params, headers=await self._headers(), timeout=20) as r:
            data = await r.json()
            return data.get("data", []) or []

TwitchAPI = TWITCHAPI