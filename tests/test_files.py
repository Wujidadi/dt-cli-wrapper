"""Path resolution, prompt-file reading and parameter-file loading"""

from pathlib import Path

import pytest


class TestResolveNamedPath:
    def test_absolute_path_is_returned_unchanged(self, mod):
        assert (mod.resolve_named_path("/abs/file", Path("/base"), ".toml")
                == Path("/abs/file"))

    def test_tilde_is_expanded(self, mod):
        assert (mod.resolve_named_path("~/file", Path("/base"), ".toml")
                == Path.home() / "file")

    @pytest.mark.parametrize("value", ["./rel", "../rel"])
    def test_dot_relative_paths_are_kept_relative_to_cwd(self, mod, value):
        assert mod.resolve_named_path(value, Path("/base"), ".toml") == Path(value)

    def test_bare_name_gets_default_extension_under_base_dir(self, mod):
        assert (mod.resolve_named_path("preset", Path("/base"), ".toml")
                == Path("/base/preset.toml"))

    def test_existing_extension_is_kept(self, mod):
        assert (mod.resolve_named_path("preset.txt", Path("/base"), ".toml")
                == Path("/base/preset.txt"))

    def test_subdirectories_are_allowed(self, mod):
        assert (mod.resolve_named_path("t2i/model/dist", Path("/base"), ".toml")
                == Path("/base/t2i/model/dist.toml"))


class TestIsCommentLine:
    @pytest.mark.parametrize("line", ["#", "//", "# note", "// note",
                                      "   # indented", "\t// tabbed"])
    def test_comment_lines(self, mod, line):
        assert mod.is_comment_line(line)

    @pytest.mark.parametrize("line", ["#hashtag", "//x", "text", "", "a # b"])
    def test_non_comment_lines(self, mod, line):
        assert not mod.is_comment_line(line)


class TestReadTextFile:
    def test_strips_comment_lines_and_surrounding_whitespace(self, mod, tmp_path):
        path = tmp_path / "p.txt"
        path.write_text("# header\n\nfirst line\n// note\n\nsecond line\n\n",
                        encoding="utf-8")
        assert mod.read_text_file(path, "prompt file") == "first line\n\nsecond line"

    def test_missing_file_dies(self, mod, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            mod.read_text_file(tmp_path / "missing.txt", "prompt file")
        assert exc.value.code == 1
        assert "prompt file not found" in capsys.readouterr().err


class TestLoadParameters:
    @pytest.fixture(autouse=True)
    def params_dir(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "PARAMETERS_DIR", tmp_path)
        return tmp_path

    def test_loads_named_file_from_parameters_dir(self, mod, params_dir, capsys):
        (params_dir / "preset.toml").write_text('model = "m.ckpt"\nsteps = 4\n')
        assert mod.load_parameters("preset") == {"model": "m.ckpt", "steps": 4}
        assert capsys.readouterr().err == ""

    def test_unknown_top_level_key_warns_but_is_kept(self, mod, params_dir, capsys):
        (params_dir / "p.toml").write_text('model = "m"\nbogus = 1\n')
        params = mod.load_parameters("p")
        assert params["bogus"] == 1
        assert 'unknown key "bogus"' in capsys.readouterr().err

    def test_missing_file_dies(self, mod, capsys):
        with pytest.raises(SystemExit):
            mod.load_parameters("nope")
        assert "parameter file not found" in capsys.readouterr().err

    def test_invalid_toml_dies(self, mod, params_dir, capsys):
        (params_dir / "bad.toml").write_text("model = \n")
        with pytest.raises(SystemExit):
            mod.load_parameters("bad")
        assert "failed to parse parameter file" in capsys.readouterr().err

    def test_shipped_presets_parse_with_known_keys_only(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "PARAMETERS_DIR", mod.TOOL_DIR / "parameters")
        for path in sorted((mod.TOOL_DIR / "parameters").rglob("*.toml")):
            name = str(path.relative_to(mod.TOOL_DIR / "parameters"))
            params = mod.load_parameters(name)
            assert params.get("model"), name
        assert capsys.readouterr().err == ""


def test_die_prints_prefixed_message_and_exits_1(mod, capsys):
    with pytest.raises(SystemExit) as exc:
        mod.die("boom")
    assert exc.value.code == 1
    assert capsys.readouterr().err == "dtgen: boom\n"
