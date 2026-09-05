"""Prompt / negative prompt resolution, affixes and the enhancement loop"""

import pytest
from prompt_enhancer import PromptEnhancerError


class TestResolvePromptText:
    @pytest.fixture(autouse=True)
    def prompts_dir(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "PROMPTS_DIR", tmp_path)
        return tmp_path

    def test_inline_prompt_wins(self, mod, make_args):
        args = make_args(prompt="inline", prompt_file="x")
        assert mod.resolve_prompt_text(args, {"prompt": "param"}) == "inline"

    def test_prompt_file_is_resolved_under_prompts_dir(self, mod, make_args, prompts_dir):
        (prompts_dir / "sub").mkdir()
        (prompts_dir / "sub" / "cat.txt").write_text("# c\na cat\n")
        assert mod.resolve_prompt_text(make_args(prompt_file="sub/cat"), {}) == "a cat"

    def test_parameter_file_prompt_is_used(self, mod, make_args):
        assert mod.resolve_prompt_text(make_args(), {"prompt": "from toml"}) == "from toml"

    def test_default_txt_is_the_last_fallback(self, mod, make_args, prompts_dir):
        (prompts_dir / "default.txt").write_text("default prompt\n")
        assert mod.resolve_prompt_text(make_args(), {}) == "default prompt"

    def test_no_prompt_anywhere_dies(self, mod, make_args, capsys):
        with pytest.raises(SystemExit):
            mod.resolve_prompt_text(make_args(), {})
        assert "no prompt given" in capsys.readouterr().err


class TestApplyPromptAffixes:
    def test_without_affixes(self, mod):
        assert mod.apply_prompt_affixes("text", {}) == "text"

    def test_prefix_and_suffix(self, mod):
        params = {"prompt_prefix": "pre", "prompt_suffix": "suf"}
        assert mod.apply_prompt_affixes("text", params) == "pre, text, suf"

    def test_empty_affixes_are_skipped(self, mod):
        params = {"prompt_prefix": "", "prompt_suffix": "suf"}
        assert mod.apply_prompt_affixes("text", params) == "text, suf"


class TestResolveNegativePrompt:
    def test_inline_wins(self, mod, make_args):
        args = make_args(negative_prompt="bad", negative_prompt_file="x")
        assert mod.resolve_negative_prompt(args, {"negative_prompt": "p"}) == "bad"

    def test_file(self, mod, make_args, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "PROMPTS_DIR", tmp_path)
        (tmp_path / "negative").mkdir()
        (tmp_path / "negative" / "n.txt").write_text("// note\nugly\n")
        args = make_args(negative_prompt_file="negative/n")
        assert mod.resolve_negative_prompt(args, {}) == "ugly"

    def test_parameter_file_fallback(self, mod, make_args):
        assert mod.resolve_negative_prompt(make_args(), {"negative_prompt": "p"}) == "p"
        assert mod.resolve_negative_prompt(make_args(), {}) is None


class TestBuildEnhancer:
    def test_maps_enhancer_section_onto_from_config(self, mod, make_args, fake_enhancer):
        fake_enhancer()
        params = {"enhancer": {"provider": "prof", "language": "zh", "model": "m"}}
        enhancer = mod.build_enhancer(make_args(), params)
        assert enhancer.from_config_args == ("prof", {"model": "m"}, "zh")
        assert params["enhancer"] == {"provider": "prof", "language": "zh", "model": "m"}

    def test_cli_language_overrides_section(self, mod, make_args, fake_enhancer):
        fake_enhancer()
        params = {"enhancer": {"language": "zh"}}
        enhancer = mod.build_enhancer(make_args(enhance_language="en"), params)
        assert enhancer.from_config_args == (None, {}, "en")

    def test_without_section(self, mod, make_args, fake_enhancer):
        fake_enhancer()
        assert mod.build_enhancer(make_args(), {}).from_config_args == (None, {}, None)


class TestEnhancePrompt:
    @pytest.fixture
    def tty(self, mod, monkeypatch):
        """Make sys.stdin look interactive and feed scripted answers to input()"""
        monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: True)
        answers = []
        prompts = []

        def fake_input(prompt=""):
            prompts.append(prompt)
            if not answers:
                raise EOFError
            return answers.pop(0)

        monkeypatch.setattr("builtins.input", fake_input)

        def feed(*values):
            answers.extend(values)
            return prompts
        return feed

    @pytest.fixture
    def no_tty(self, mod, monkeypatch):
        monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: False)

    def test_build_failure_dies(self, mod, make_args, fake_enhancer, capsys):
        fake_enhancer(error=PromptEnhancerError("no such profile"))
        with pytest.raises(SystemExit):
            mod.enhance_prompt("t", make_args(enhance="photo"), {})
        assert "no such profile" in capsys.readouterr().err

    def test_non_interactive_returns_first_result(self, mod, make_args, fake_enhancer,
                                                  no_tty, capsys):
        instances = fake_enhancer("better")
        result = mod.enhance_prompt("t", make_args(enhance="photo"), {})
        assert result == "better"
        assert instances[0].calls == [("t", "photo", None)]
        err = capsys.readouterr().err
        assert "preset photo" in err and "fake provider" in err
        assert "----- enhanced prompt -----\nbetter\n" in err

    def test_enhance_once_skips_loop_even_on_tty(self, mod, make_args, fake_enhancer, tty):
        fake_enhancer("once")
        args = make_args(enhance="photo", enhance_once=True)
        assert mod.enhance_prompt("t", args, {}) == "once"
        assert tty() == []

    def test_enhance_only_is_silent_about_the_result(self, mod, make_args, fake_enhancer,
                                                     no_tty, capsys):
        fake_enhancer("quiet")
        args = make_args(enhance="photo", enhance_only=True)
        assert mod.enhance_prompt("t", args, {}) == "quiet"
        assert "enhanced prompt" not in capsys.readouterr().err

    def test_custom_instruction_mode_label(self, mod, make_args, fake_enhancer,
                                           no_tty, capsys):
        instances = fake_enhancer("custom")
        args = make_args(enhance_instruction="make it blue")
        assert mod.enhance_prompt("t", args, {}) == "custom"
        assert instances[0].calls == [("t", None, "make it blue")]
        assert "custom instruction" in capsys.readouterr().err

    def test_non_interactive_failure_dies(self, mod, make_args, fake_enhancer,
                                          no_tty, capsys):
        fake_enhancer(PromptEnhancerError("timeout"))
        with pytest.raises(SystemExit):
            mod.enhance_prompt("t", make_args(enhance="photo"), {})
        assert "prompt enhancement failed: timeout" in capsys.readouterr().err

    def test_interactive_generate(self, mod, make_args, fake_enhancer, tty):
        fake_enhancer("v1")
        tty("g")
        assert mod.enhance_prompt("t", make_args(enhance="photo"), {}) == "v1"

    def test_interactive_failure_keeps_prompt_and_asks_again(self, mod, make_args,
                                                             fake_enhancer, tty, capsys):
        fake_enhancer(PromptEnhancerError("flaky"), "v2")
        tty("e", "g")
        assert mod.enhance_prompt("t", make_args(enhance="photo"), {}) == "v2"
        err = capsys.readouterr().err
        assert "enhancement failed, prompt unchanged: flaky" in err

    def test_enhance_again_feeds_previous_result(self, mod, make_args, fake_enhancer, tty):
        instances = fake_enhancer("v1", "v2")
        tty("e", "g")
        assert mod.enhance_prompt("t", make_args(enhance="photo"), {}) == "v2"
        assert [c[0] for c in instances[0].calls] == ["t", "v1"]

    def test_new_instruction_is_used_on_next_pass(self, mod, make_args, fake_enhancer, tty):
        instances = fake_enhancer("v1", "v2")
        tty("i", "add fog", "g")
        args = make_args(enhance="photo", enhance_instruction="old")
        assert mod.enhance_prompt("t", args, {}) == "v2"
        assert [c[2] for c in instances[0].calls] == ["old", "add fog"]

    def test_empty_instruction_keeps_previous_one(self, mod, make_args, fake_enhancer,
                                                  tty, capsys):
        instances = fake_enhancer("v1", "v2")
        tty("i", "   ", "g")
        args = make_args(enhance="photo", enhance_instruction="old")
        assert mod.enhance_prompt("t", args, {}) == "v2"
        assert [c[2] for c in instances[0].calls] == ["old", "old"]
        assert "empty instruction, keeping the previous one" in capsys.readouterr().err

    def test_unknown_choice_is_asked_again(self, mod, make_args, fake_enhancer, tty):
        fake_enhancer("v1")
        prompts = tty("x", "", "G")
        assert mod.enhance_prompt("t", make_args(enhance="photo"), {}) == "v1"
        assert len(prompts) == 3

    def test_quit_exits_zero(self, mod, make_args, fake_enhancer, tty):
        fake_enhancer("v1")
        tty("q")
        with pytest.raises(SystemExit) as exc:
            mod.enhance_prompt("t", make_args(enhance="photo"), {})
        assert exc.value.code == 0

    def test_eof_at_menu_exits_zero(self, mod, make_args, fake_enhancer, tty):
        fake_enhancer("v1")
        tty()
        with pytest.raises(SystemExit) as exc:
            mod.enhance_prompt("t", make_args(enhance="photo"), {})
        assert exc.value.code == 0

    def test_eof_at_instruction_exits_zero(self, mod, make_args, fake_enhancer, tty):
        fake_enhancer("v1")
        tty("i")
        with pytest.raises(SystemExit) as exc:
            mod.enhance_prompt("t", make_args(enhance="photo"), {})
        assert exc.value.code == 0
