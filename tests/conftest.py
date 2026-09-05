"""Load the extensionless dtgen script as an importable module and share fakes"""

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

DTGEN_PATH = Path(__file__).resolve().parent.parent / "dtgen"


def _load_dtgen():
    loader = SourceFileLoader("dtgen", str(DTGEN_PATH))
    spec = importlib.util.spec_from_loader("dtgen", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dtgen"] = module
    loader.exec_module(module)
    return module


dtgen = _load_dtgen()


@pytest.fixture
def mod():
    return dtgen


@pytest.fixture
def make_args():
    """Build an argparse-like namespace with every dtgen option defaulted"""
    def factory(**overrides):
        defaults = dict(
            parameter_file=None, prompt=None, prompt_file=None,
            negative_prompt=None, negative_prompt_file=None,
            enhance=None, enhance_instruction=None, enhance_language=None,
            enhance_once=False, enhance_only=False,
            image=None, model=None, seed=None, output=None, dry_run=False,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)
    return factory


class FakeProvider:
    def describe(self):
        return "fake provider"


class FakeEnhancer:
    """Stand-in for prompt_enhancer.Enhancer: `replies` are returned (or
    raised, when they are exceptions) in order by successive enhance() calls"""
    instances = []

    def __init__(self, replies):
        self.provider = FakeProvider()
        self.replies = list(replies)
        self.calls = []
        self.from_config_args = None
        FakeEnhancer.instances.append(self)

    def enhance(self, text, *, preset=None, instruction=None):
        self.calls.append((text, preset, instruction))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def fake_enhancer(monkeypatch):
    """Patch dtgen.Enhancer so from_config() yields a FakeEnhancer with
    the given replies; returns the factory used to configure it"""
    FakeEnhancer.instances.clear()
    state = {"replies": ["enhanced"], "error": None}

    class Patched:
        @classmethod
        def from_config(cls, provider, overrides, *, language=None):
            if state["error"] is not None:
                raise state["error"]
            instance = FakeEnhancer(state["replies"])
            instance.from_config_args = (provider, overrides, language)
            return instance

    monkeypatch.setattr(dtgen, "Enhancer", Patched)

    def configure(*replies, error=None):
        state["replies"] = list(replies) or ["enhanced"]
        state["error"] = error
        return FakeEnhancer.instances

    return configure


def make_png(width=4, height=3, extra_chunks=(), with_idat=True):
    """Minimal PNG byte string: IHDR, optional extra chunks, IDAT, IEND"""
    import struct
    import zlib

    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload)))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = dtgen.PNG_SIGNATURE + chunk(b"IHDR", ihdr)
    for kind, payload in extra_chunks:
        data += chunk(kind, payload)
    if with_idat:
        raw = b"".join(b"\x00" + b"\x00" * (width * 3) for _ in range(height))
        data += chunk(b"IDAT", zlib.compress(raw))
    data += chunk(b"IEND", b"")
    return data


def parse_chunks(data):
    """Return [(type, payload)] for a PNG byte string"""
    import struct
    assert data.startswith(dtgen.PNG_SIGNATURE)
    pos = 8
    chunks = []
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        chunks.append((kind, payload))
        pos += 12 + length
    return chunks
