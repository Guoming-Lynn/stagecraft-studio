"""Keep secrets in keyring when usable, otherwise only in process memory."""

from __future__ import annotations

try:
    import keyring
except ImportError:  # pragma: no cover - exercised in minimal installs
    keyring = None  # type: ignore[assignment]


class Credentials:
    def __init__(self) -> None:
        self._session: dict[str, str] = {}

    def put(self, credential_id: str, secret: str, remember: bool) -> str:
        self._session[credential_id] = secret
        if remember and keyring is not None:
            try:
                keyring.set_password("stagecraft-studio", credential_id, secret)
                return "credential_store"
            except Exception:
                return "session"
        self.forget_stored(credential_id)
        return "session" if secret else "none"

    def get(self, credential_id: str) -> tuple[str, str]:
        if credential_id in self._session:
            secret = self._session[credential_id]
            stored = self._stored(credential_id)
            return secret, "credential_store" if stored == secret and secret else "session"
        stored = self._stored(credential_id)
        return (stored, "credential_store") if stored else ("", "none")

    def _stored(self, credential_id: str) -> str:
        if keyring is None:
            return ""
        try:
            return keyring.get_password("stagecraft-studio", credential_id) or ""
        except Exception:
            return ""

    def forget_stored(self, credential_id: str) -> None:
        if keyring is None:
            return
        try:
            if self._stored(credential_id):
                keyring.delete_password("stagecraft-studio", credential_id)
        except Exception:
            return

    def forget(self, credential_id: str) -> None:
        self._session.pop(credential_id, None)
        self.forget_stored(credential_id)

    def clear(self) -> None:
        self._session.clear()
