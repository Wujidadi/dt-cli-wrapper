"""Image interrogation: backend construction, options and the review loop"""

from pathlib import Path

import pytest
from image_interrogator import ImageInterrogatorError
from prompt_enhancer import PromptEnhancerError


class TestBuildInterrogator:
    def test_maps_section_onto_from_config(self, mod, make_args, fake_interrogator):
        fake_interrogator()
        params = {"interrogator": {"provider": "prof", "language": "zh", "model": "m",
                                   "preset": "tags", "explicit": True, "url": "u"}}
        interrogator = mod.build_interrogator(make_args(), params)
        assert interrogator.from_config_args == ("prof", {"model": "m", "url": "u"}, "zh")
        assert params["interrogator"]["preset"] == "tags"

    def test_cli_overrides_section(self, mod, make_args, fake_interrogator):
        fake_interrogator()
        params = {"interrogator": {"provider": "prof", "language": "zh", "model": "m"}}
        args = make_args(interrogate_provider="cli", interrogate_model="cm",
                         interrogate_language="en")
        assert mod.build_interrogator(args, params).from_config_args == ("cli", {"model": "cm"}, "en")

    def test_without_section(self, mod, make_args, fake_interrogator):
        fake_interrogator()
        assert mod.build_interrogator(make_args(), {}).from_config_args == (None, {}, None)


class TestInterrogateOptions:
    def test_defaults(self, mod, make_args):
        assert mod.interrogate_options(make_args(), {}) == (mod.DEFAULT_INTERROGATOR_PRESET, False)

    def test_section_then_cli(self, mod, make_args):
        params = {"interrogator": {"preset": "tags", "explicit": True}}
        assert mod.interrogate_options(make_args(), params) == ("tags", True)
        args = make_args(interrogate_preset="concise")
        assert mod.interrogate_options(args, params) == ("concise", True)
        args = make_args(interrogate_explicit=True)
        assert mod.interrogate_options(args, {}) == (mod.DEFAULT_INTERROGATOR_PRESET, True)


class TestResolveInterrogateImage:
    def test_explicit_path_is_expanded(self, mod, make_args, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert mod.resolve_interrogate_image(make_args(interrogate="~/a.png")) == tmp_path / "a.png"

    def test_bare_flag_uses_the_img2img_input(self, mod, make_args):
        args = make_args(interrogate=mod.INTERROGATE_FROM_IMAGE, image="in.png")
        assert mod.resolve_interrogate_image(args) == Path("in.png")

    def test_bare_flag_without_image_dies(self, mod, make_args, capsys):
        with pytest.raises(SystemExit):
            mod.resolve_interrogate_image(make_args(interrogate=mod.INTERROGATE_FROM_IMAGE))
        assert "--image" in capsys.readouterr().err


class TestInterrogateImage:
    @pytest.fixture
    def tty(self, mod, monkeypatch):
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

    def test_build_failure_dies(self, mod, make_args, fake_interrogator, capsys):
        fake_interrogator(error=ImageInterrogatorError("no such profile"))
        with pytest.raises(SystemExit):
            mod.interrogate_image(make_args(interrogate="a.png"), {})
        assert "no such profile" in capsys.readouterr().err

    def test_non_interactive_returns_first_result(self, mod, make_args, fake_interrogator,
                                                  no_tty, capsys):
        instances = fake_interrogator("a cat")
        args = make_args(interrogate="a.png", interrogate_instruction="fur",
                         interrogate_explicit=True)
        assert mod.interrogate_image(args, {"interrogator": {"preset": "tags"}}) == "a cat"
        assert instances[0].calls == [(Path("a.png"), "tags", "fur", True)]
        err = capsys.readouterr().err
        assert "interrogating a.png (fake provider, preset tags)" in err
        assert "----- interrogated prompt -----" in err and "a cat" in err

    def test_once_skips_loop_even_on_tty(self, mod, make_args, fake_interrogator, tty):
        fake_interrogator("a cat")
        args = make_args(interrogate="a.png", interrogate_once=True)
        assert mod.interrogate_image(args, {}) == "a cat"
        assert tty() == []

    def test_only_is_silent_about_the_result(self, mod, make_args, fake_interrogator,
                                             tty, capsys):
        fake_interrogator("a cat")
        args = make_args(interrogate="a.png", interrogate_only=True)
        assert mod.interrogate_image(args, {}) == "a cat"
        assert "-----" not in capsys.readouterr().err

    def test_non_interactive_failure_dies(self, mod, make_args, fake_interrogator,
                                          no_tty, capsys):
        fake_interrogator(ImageInterrogatorError("boom"))
        with pytest.raises(SystemExit):
            mod.interrogate_image(make_args(interrogate="a.png"), {})
        assert "image interrogation failed: boom" in capsys.readouterr().err

    def test_interactive_first_failure_dies(self, mod, make_args, fake_interrogator,
                                            tty, capsys):
        fake_interrogator(ImageInterrogatorError("boom"))
        with pytest.raises(SystemExit):
            mod.interrogate_image(make_args(interrogate="a.png"), {})
        assert "image interrogation failed: boom" in capsys.readouterr().err

    def test_interactive_generate(self, mod, make_args, fake_interrogator, tty):
        fake_interrogator("a cat")
        tty("g")
        assert mod.interrogate_image(make_args(interrogate="a.png"), {}) == "a cat"

    def test_re_interrogate(self, mod, make_args, fake_interrogator, tty):
        instances = fake_interrogator("first", "second")
        tty("r", "g")
        assert mod.interrogate_image(make_args(interrogate="a.png"), {}) == "second"
        assert len(instances[0].calls) == 2

    def test_later_failure_keeps_prompt_and_asks_again(self, mod, make_args,
                                                       fake_interrogator, tty, capsys):
        fake_interrogator("first", ImageInterrogatorError("boom"))
        tty("r", "g")
        assert mod.interrogate_image(make_args(interrogate="a.png"), {}) == "first"
        assert "prompt unchanged: boom" in capsys.readouterr().err

    def test_new_instruction_is_used_on_next_pass(self, mod, make_args, fake_interrogator, tty):
        instances = fake_interrogator("first", "second")
        tty("i", "focus on fur", "g")
        assert mod.interrogate_image(make_args(interrogate="a.png"), {}) == "second"
        assert instances[0].calls[1][2] == "focus on fur"

    def test_empty_instruction_keeps_previous_one(self, mod, make_args, fake_interrogator,
                                                  tty, capsys):
        instances = fake_interrogator("first", "second")
        tty("i", "", "g")
        args = make_args(interrogate="a.png", interrogate_instruction="old")
        assert mod.interrogate_image(args, {}) == "second"
        assert instances[0].calls[1][2] == "old"
        assert "keeping the previous one" in capsys.readouterr().err

    def test_eof_at_instruction_exits_zero(self, mod, make_args, fake_interrogator, tty):
        fake_interrogator("first")
        tty("i")
        with pytest.raises(SystemExit) as e:
            mod.interrogate_image(make_args(interrogate="a.png"), {})
        assert e.value.code == 0

    def test_enhance_from_menu(self, mod, make_args, fake_interrogator, fake_enhancer,
                               tty, capsys):
        fake_interrogator("a cat")
        enhancers = fake_enhancer("a richer cat")
        tty("e", "g", "g")
        args = make_args(interrogate="a.png")
        assert mod.interrogate_image(args, {}) == "a richer cat"
        assert enhancers[0].calls == [("a cat", mod.DEFAULT_PRESET, None)]
        assert args.enhance == mod.DEFAULT_PRESET
        assert "a richer cat" in capsys.readouterr().err

    def test_enhance_from_menu_keeps_explicit_enhance_flags(self, mod, make_args,
                                                            fake_interrogator, fake_enhancer,
                                                            tty):
        fake_interrogator("a cat")
        enhancers = fake_enhancer("styled")
        tty("e", "g", "g")
        args = make_args(interrogate="a.png", enhance="ghibli-watercolor")
        assert mod.interrogate_image(args, {}) == "styled"
        assert enhancers[0].calls[0][1] == "ghibli-watercolor"

    def test_unknown_choice_is_asked_again(self, mod, make_args, fake_interrogator, tty):
        fake_interrogator("a cat")
        prompts = tty("x", "g")
        assert mod.interrogate_image(make_args(interrogate="a.png"), {}) == "a cat"
        assert len(prompts) == 2

    def test_quit_exits_zero(self, mod, make_args, fake_interrogator, tty):
        fake_interrogator("a cat")
        tty("q")
        with pytest.raises(SystemExit) as e:
            mod.interrogate_image(make_args(interrogate="a.png"), {})
        assert e.value.code == 0

    def test_eof_at_menu_exits_zero(self, mod, make_args, fake_interrogator, tty):
        fake_interrogator("a cat")
        tty()
        with pytest.raises(SystemExit) as e:
            mod.interrogate_image(make_args(interrogate="a.png"), {})
        assert e.value.code == 0
