"""The part of uharfbuzz's API that Kaker Theng uses, on top of harfbuzzjs.

uharfbuzz has no Pyodide build. This shim lets backend/app run unchanged in
the browser: the page imports harfbuzzjs and puts it on globalThis.harfbuzz.

One difference matters: uharfbuzz's Buffer.add_str numbers clusters by code
point (a Python str is code points); harfbuzzjs's addText adds UTF-16, so
clusters would be UTF-16 offsets. Code points are added one by one here with
their index as the cluster, so results match exactly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import js
from pyodide.ffi import create_proxy, to_js

_hb = js.harfbuzz


class Blob:
    def __init__(self, data: bytes):
        self._js = _hb.Blob.new(to_js(bytes(data)))


class Face:
    def __init__(self, blob: Blob, index: int = 0):
        self._js = _hb.Face.new(blob._js, index)


class Font:
    def __init__(self, face: Face):
        self._js = _hb.Font.new(face._js)


@dataclass
class GlyphInfo:
    codepoint: int
    cluster: int


@dataclass
class GlyphPosition:
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int


class Buffer:
    def __init__(self):
        self._js = _hb.Buffer.new()
        self._message_func = None

    def add_str(self, text: str):
        for index, ch in enumerate(text):
            self._js.add(ord(ch), index)

    def guess_segment_properties(self):
        self._js.guessSegmentProperties()

    def set_message_func(self, fn):
        self._message_func = fn

    @property
    def glyph_infos(self) -> list[GlyphInfo]:
        return [GlyphInfo(d["codepoint"], d["cluster"]) for d in json.loads(js.JSON.stringify(self._js.getGlyphInfos()))]

    @property
    def glyph_positions(self) -> list[GlyphPosition]:
        return [
            GlyphPosition(d["xAdvance"], d["yAdvance"], d["xOffset"], d["yOffset"])
            for d in json.loads(js.JSON.stringify(self._js.getGlyphPositions()))
        ]


def shape(font: Font, buf: Buffer, features: dict | None = None):
    feats = [_hb.Feature.new(tag, int(value)) for tag, value in (features or {}).items()]
    proxy = None
    if buf._message_func is not None:
        # harfbuzzjs hands back a new wrapper around the same buffer; the
        # Python callback reads `buf` itself, as with uharfbuzz.
        proxy = create_proxy(lambda _b, _f, message: bool(buf._message_func(message)))
        buf._js.setMessageFunc(proxy)
    try:
        _hb.shape(font._js, buf._js, to_js(feats))
    finally:
        if proxy is not None:
            proxy.destroy()
