from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path

from lbs_delivery.errors import DeliveryError, Status
from lbs_delivery.mtext_adapter import call_adapter
from lbs_delivery.resources import (
    publish_server_sync,
    stage_resources,
)


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return self._body


class ResourceTests(unittest.TestCase):
    def test_stage_and_atomic_publication(self) -> None:
        config = {
            "code": "FI",
            "repository": "mtext-fi",
            "subsystem": "LOMS",
            "projects": [{"name": "Base", "source_path": "Base"}],
            "handover_profiles": {
                "FKT": {"assignment": "LOMS000066", "stage": "FKTE"},
                "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            staging = root / "staging"
            target = root / "serverSync"
            (source / "Base").mkdir(parents=True)
            (source / "Base/value.txt").write_text("new", encoding="utf-8")
            (target / "Base").mkdir(parents=True)
            (target / "Base/value.txt").write_text("old", encoding="utf-8")

            self.assertEqual(
                stage_resources(source, staging, config["projects"]), ["Base"]
            )
            publish_server_sync(staging, target)
            self.assertEqual((target / "Base/value.txt").read_text(), "new")
            self.assertFalse(any(path.name.startswith(".Base.") for path in target.iterdir()))


class AdapterTests(unittest.TestCase):
    def test_documented_2xx_is_accepted(self) -> None:
        response = call_adapter(
            "https://adapter.example.test/vMtextAdapter/sync",
            {"mandant": "MAN", "institut": "INR"},
            opener=lambda *_args, **_kwargs: _Response(200, b"accepted"),
        )
        self.assertEqual((response.status, response.body), (200, "accepted"))

    def test_http_400_and_non_https_are_rejected(self) -> None:
        error = urllib.error.HTTPError(
            "https://adapter.example.test", 400, "Bad Request", {}, None
        )
        error.read = lambda _limit: b"Could not receive Message"  # type: ignore[method-assign]
        with self.assertRaises(DeliveryError) as raised:
            call_adapter(
                "https://adapter.example.test/vMtextAdapter/sync",
                {},
                opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
            )
        self.assertEqual(raised.exception.status, Status.ADAPTER_FAILED)
        with self.assertRaises(DeliveryError):
            call_adapter("http://adapter.example.test/sync", {})


if __name__ == "__main__":
    unittest.main()
