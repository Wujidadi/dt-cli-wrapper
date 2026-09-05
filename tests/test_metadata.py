"""PNG metadata: chunk helpers, XMP construction and embedding"""

import json
import struct
import zlib

import pytest

from conftest import make_png, parse_chunks


def test_xml_escape(mod):
    assert mod.xml_escape("a&b<c>\nd") == "a&amp;b&lt;c&gt;&#xA;d"


def test_png_chunk_layout_and_crc(mod):
    chunk = mod.png_chunk(b"tEXt", b"payload")
    assert chunk[:4] == struct.pack(">I", 7)
    assert chunk[4:8] == b"tEXt"
    assert chunk[8:15] == b"payload"
    assert chunk[15:] == struct.pack(">I", zlib.crc32(b"tEXtpayload"))


def test_exif_payload_encodes_dimensions_in_big_endian_tiff(mod):
    payload = mod.exif_payload(1280, 720)
    assert payload.startswith(b"MM\x00*\x00\x00\x00\x08")
    # IFD0 has one entry (ExifIFD pointer, tag 0x8769) pointing at offset 0x1a
    assert payload[8:10] == b"\x00\x01"
    assert payload[10:12] == b"\x87\x69"
    exif_ifd = payload[0x1a:]
    assert exif_ifd[:2] == b"\x00\x02"
    assert exif_ifd[2:4] == b"\xa0\x02"
    assert struct.unpack(">I", exif_ifd[10:14]) == (1280,)
    assert exif_ifd[14:16] == b"\xa0\x03"
    assert struct.unpack(">I", exif_ifd[22:26]) == (720,)
    assert payload.endswith(b"\x00\x00\x00\x00")


FULL_PARAMS = {
    "steps": 8, "cfg": 1, "strength": 0.5, "frames": 1,
    "config": {
        "sampler": 17, "seedMode": 2, "shift": 3, "maskBlur": 1.5,
        "loras": [{"file": "a.ckpt", "weight": 0.8}, {}],
    },
}


def _user_comment(xmp):
    start = xmp.index("<exif:UserComment>")
    li = xmp.index('<rdf:li xml:lang="x-default">', start) + len('<rdf:li xml:lang="x-default">')
    end = xmp.index("</rdf:li>", li)
    raw = xmp[li:end]
    unescaped = (raw.replace("&#xA;", "\n").replace("&lt;", "<")
                 .replace("&gt;", ">").replace("&amp;", "&"))
    return json.loads(unescaped)


def test_build_xmp_with_full_parameters(mod):
    xmp = mod.build_xmp("a <cat>", "ugly & bad", "m.ckpt", 42, 640, 480, FULL_PARAMS)
    assert "<xmp:CreatorTool>Draw Things</xmp:CreatorTool>" in xmp
    description = xmp[xmp.index("<dc:description>"):xmp.index("</dc:description>")]
    assert "a &lt;cat&gt;&#xA;-ugly &amp; bad&#xA;" in description
    summary = description.split("&#xA;")[-1]
    assert summary.startswith(
        "Steps: 8, Sampler: UniPC Trailing, Guidance Scale: 1.0, Seed: 42, "
        "Size: 640x480, Model: m.ckpt, Strength: 0.5, Seed Mode: Scale Alike, "
        "Shift: 3.0, LoRA Model: a.ckpt, LoRA Weight: 0.8, "
        "LoRA Model: , LoRA Weight: 1.0")

    comment = _user_comment(xmp)
    assert comment["c"] == "a <cat>"
    assert comment["uc"] == "ugly & bad"
    assert comment["model"] == "m.ckpt"
    assert comment["seed"] == 42
    assert comment["size"] == "640x480"
    assert comment["steps"] == 8
    assert comment["scale"] == 1
    assert comment["strength"] == 0.5
    assert comment["sampler"] == "UniPC Trailing"
    assert comment["seed_mode"] == "Scale Alike"
    assert comment["shift"] == 3
    assert comment["mask_blur"] == 1.5
    assert comment["lora"] == [{"model": "a.ckpt", "weight": 0.8},
                               {"model": "", "weight": 1}]
    v2 = comment["v2"]
    assert v2["model"] == "m.ckpt" and v2["seed"] == 42
    assert v2["width"] == 640 and v2["height"] == 480
    assert v2["steps"] == 8 and v2["guidanceScale"] == 1
    assert v2["strength"] == 0.5 and v2["numFrames"] == 1
    assert v2["sampler"] == 17 and v2["loras"] == FULL_PARAMS["config"]["loras"]
    # The original config dictionary is left untouched
    assert "model" not in FULL_PARAMS["config"]


def test_build_xmp_with_minimal_parameters(mod):
    xmp = mod.build_xmp("p", None, "m", 1, 8, 8, {})
    description = xmp[xmp.index("<dc:description>"):xmp.index("</dc:description>")]
    assert "p&#xA;Seed: 1, Size: 8x8, Model: m</rdf:li>" in description
    comment = _user_comment(xmp)
    assert comment["uc"] == ""
    for key in ("steps", "scale", "strength", "sampler", "seed_mode",
                "shift", "mask_blur", "lora"):
        assert key not in comment
    assert comment["v2"] == {"model": "m", "seed": 1, "width": 8, "height": 8}


def test_build_xmp_ignores_unknown_enum_values(mod):
    params = {"config": {"sampler": 99, "seedMode": 99}}
    comment = _user_comment(mod.build_xmp("p", "", "m", 1, 8, 8, params))
    assert "sampler" not in comment and "seed_mode" not in comment


class TestEmbedPngMetadata:
    def test_inserts_exif_and_xmp_before_idat(self, mod, tmp_path, capsys):
        out = tmp_path / "o.png"
        out.write_bytes(make_png(5, 7, extra_chunks=[(b"tEXt", b"k\x00v")]))
        mod.embed_png_metadata(out, "prompt", "neg", "m", 9, {"steps": 2})
        assert capsys.readouterr().err == ""
        kinds = [k for k, _ in parse_chunks(out.read_bytes())]
        assert kinds == [b"IHDR", b"tEXt", b"eXIf", b"iTXt", b"IDAT", b"IEND"]
        chunks = dict(parse_chunks(out.read_bytes()))
        assert chunks[b"eXIf"] == mod.exif_payload(5, 7)
        itxt = chunks[b"iTXt"]
        assert itxt.startswith(b"XML:com.adobe.xmp\x00\x00\x00\x00\x00")
        xmp = itxt[len(b"XML:com.adobe.xmp\x00\x00\x00\x00\x00"):].decode("utf-8")
        assert xmp == mod.build_xmp("prompt", "neg", "m", 9, 5, 7, {"steps": 2})

    def test_result_is_a_valid_png_for_the_standard_library(self, mod, tmp_path):
        out = tmp_path / "o.png"
        out.write_bytes(make_png(3, 2))
        mod.embed_png_metadata(out, "p", None, "m", 1, {})
        for kind, payload in parse_chunks(out.read_bytes()):
            assert kind.isalpha()
        data = out.read_bytes()
        # Every chunk CRC must still verify
        pos = 8
        while pos < len(data):
            length, = struct.unpack(">I", data[pos:pos + 4])
            body = data[pos + 4:pos + 8 + length]
            crc, = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
            assert crc == zlib.crc32(body)
            pos += 12 + length

    @pytest.mark.parametrize("data", [b"\xff\xd8\xff\xe0 jpeg", b"", b"\x89PNG\r\n\x1a\nXXXXXXXX"])
    def test_non_png_is_left_alone(self, mod, tmp_path, capsys, data):
        out = tmp_path / "o.png"
        out.write_bytes(data)
        mod.embed_png_metadata(out, "p", None, "m", 1, {})
        assert out.read_bytes() == data
        assert "not a PNG, metadata not embedded" in capsys.readouterr().err

    def test_missing_idat_is_left_alone(self, mod, tmp_path, capsys):
        out = tmp_path / "o.png"
        data = make_png(with_idat=False)
        out.write_bytes(data)
        mod.embed_png_metadata(out, "p", None, "m", 1, {})
        assert out.read_bytes() == data
        assert "no IDAT chunk found" in capsys.readouterr().err
