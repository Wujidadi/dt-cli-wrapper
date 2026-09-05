"""Output naming, flag assembly and the main() command pipeline"""

import os
import runpy
import shlex
import stat
import sys
from types import SimpleNamespace

import pytest

from conftest import DTGEN_PATH, make_png, parse_chunks


class TestResolveOutput:
    @pytest.fixture(autouse=True)
    def frozen_time(self, mod, monkeypatch):
        monkeypatch.setattr(mod.time, "time", lambda: 1700000000.9)

    def test_defaults_to_cwd_and_png(self, mod, make_args, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        out = mod.resolve_output(make_args(), {}, 7)
        assert out == tmp_path / "1700000000-7.png"

    def test_creates_output_dir_recursively(self, mod, make_args, tmp_path):
        target = tmp_path / "a" / "b"
        out = mod.resolve_output(make_args(output=str(target)), {"output_ext": ".jpg"}, 7)
        assert target.is_dir()
        assert out == target / "1700000000-7.jpg"

    def test_tilde_in_output_is_expanded(self, mod, make_args, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        out = mod.resolve_output(make_args(output="~/pics"), {}, 1)
        assert out.parent == tmp_path / "pics"

    def test_output_path_that_is_a_file_dies(self, mod, make_args, tmp_path, capsys):
        target = tmp_path / "file"
        target.write_text("x")
        with pytest.raises(SystemExit):
            mod.resolve_output(make_args(output=str(target)), {}, 1)
        assert "exists and is not a directory" in capsys.readouterr().err


class TestBackendArgs:
    def test_all_flags(self, mod):
        cmd = []
        mod.append_backend_args(cmd, {
            "cloud_compute": True, "remote": True, "remote_tls": False,
            "remote_url": "host", "remote_port": 7859, "remote_shared_secret": "s",
            "api_key": "k", "cloud_api_base_url": "https://x", "models_dir": "/m",
        })
        assert cmd == [
            "--cloud-compute", "--remote", "--no-remote-tls",
            "--remote-url", "host", "--remote-port", "7859",
            "--remote-shared-secret", "s", "--api-key", "k",
            "--cloud-api-base-url", "https://x", "--models-dir", "/m",
        ]

    def test_remote_tls_true_and_falsy_switches(self, mod):
        cmd = []
        mod.append_backend_args(cmd, {"cloud_compute": False, "remote": False,
                                      "remote_tls": True})
        assert cmd == ["--remote-tls"]

    def test_empty(self, mod):
        cmd = []
        mod.append_backend_args(cmd, {})
        assert cmd == []


class TestOptionArgs:
    def test_all_flags(self, mod):
        cmd = []
        mod.append_option_args(cmd, {"download_missing": True, "disable_preview": True,
                                     "offline": True})
        assert cmd == ["--download-missing", "--disable-preview", "--offline"]

    def test_negated_and_absent(self, mod):
        cmd = []
        mod.append_option_args(cmd, {"download_missing": False, "disable_preview": False})
        assert cmd == ["--no-download-missing"]
        cmd = []
        mod.append_option_args(cmd, {})
        assert cmd == []


class FakeRun:
    """Replacement for subprocess.run that records the command and, optionally,
    writes an output file the way draw-things-cli would"""

    def __init__(self, returncode=0, write=None, raise_not_found=False):
        self.returncode = returncode
        self.write = write
        self.raise_not_found = raise_not_found
        self.commands = []

    def __call__(self, cmd):
        self.commands.append(list(cmd))
        if self.raise_not_found:
            raise FileNotFoundError(cmd[0])
        if self.write is not None:
            from pathlib import Path
            Path(cmd[cmd.index("--output") + 1]).write_bytes(self.write)
        return SimpleNamespace(returncode=self.returncode)


@pytest.fixture
def env(mod, tmp_path, monkeypatch):
    """Isolated parameters/ and prompts/ dirs, cwd in tmp_path, frozen clock"""
    params_dir = tmp_path / "parameters"
    prompts_dir = tmp_path / "prompts"
    params_dir.mkdir()
    prompts_dir.mkdir()
    monkeypatch.setattr(mod, "PARAMETERS_DIR", params_dir)
    monkeypatch.setattr(mod, "PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr(mod.time, "time", lambda: 1700000000)
    monkeypatch.chdir(tmp_path)
    run = FakeRun()
    monkeypatch.setattr(mod.subprocess, "run", run)

    def main(*argv):
        monkeypatch.setattr(sys, "argv", ["dtgen", *argv])
        mod.main()

    return SimpleNamespace(root=tmp_path, params=params_dir, prompts=prompts_dir,
                           run=run, main=main)


def _dry_run(env, capsys, *argv):
    argv = list(argv)
    split = argv.index("--") if "--" in argv else len(argv)
    env.main(*argv[:split], "--dry-run", *argv[split:])
    out, err = capsys.readouterr()
    assert err == ""
    return shlex.split(out.strip())


class TestMainDryRun:
    def test_minimal_command(self, env, capsys):
        cmd = _dry_run(env, capsys, "-m", "m.ckpt", "-p", "hello", "-s", "5")
        assert cmd == ["draw-things-cli", "generate", "--model", "m.ckpt",
                       "--prompt", "hello", "--seed", "5",
                       "--output", str(env.root / "1700000000-5.png")]
        assert env.run.commands == []

    def test_full_parameter_file(self, env, capsys):
        (env.params / "full.toml").write_text("""
model = "m.ckpt"
prompt = "toml prompt"
negative_prompt = "neg"
prompt_prefix = "pre"
prompt_suffix = "suf"
output_ext = "jpg"
steps = 4
cfg = 1.5
width = 448
height = 448
frames = 1
strength = 0.7
seed = 123

[config]
sampler = 17
loras = []

[backend]
models_dir = "/models"

[options]
offline = true
""")
        cmd = _dry_run(env, capsys, "-P", "full", "-i", "~/in.png", "-o", "out",
                       "--", "--extra", "1")
        assert cmd == [
            "draw-things-cli", "generate", "--model", "m.ckpt",
            "--prompt", "pre, toml prompt, suf", "--negative-prompt", "neg",
            "--image", os.path.expanduser("~/in.png"),
            "--steps", "4", "--cfg", "1.5", "--width", "448", "--height", "448",
            "--frames", "1", "--strength", "0.7", "--seed", "123",
            "--config-json", '{"sampler": 17, "loras": []}',
            "--models-dir", "/models", "--offline",
            "--output", "out/1700000000-123.jpg",
            "--extra", "1",
        ]
        assert (env.root / "out").is_dir()

    def test_cli_overrides_parameter_file(self, env, capsys):
        (env.params / "p.toml").write_text('model = "a"\nseed = 1\nnegative_prompt = "x"\n')
        (env.prompts / "n.txt").write_text("from file")
        cmd = _dry_run(env, capsys, "-P", "p", "-p", "hi", "-m", "b", "-s", "2", "-N", "n")
        assert cmd[2:4] == ["--model", "b"]
        assert cmd[cmd.index("--negative-prompt") + 1] == "from file"
        assert cmd[cmd.index("--seed") + 1] == "2"

    def test_random_seed_when_unspecified(self, env, capsys, mod, monkeypatch):
        class Rng:
            def randrange(self, n):
                assert n == 2 ** 32
                return 424242
        monkeypatch.setattr(mod.random, "SystemRandom", lambda: Rng())
        cmd = _dry_run(env, capsys, "-m", "m", "-p", "x")
        assert cmd[cmd.index("--seed") + 1] == "424242"
        assert cmd[-1].endswith("1700000000-424242.png")

    def test_prompt_file_and_default_prompt(self, env, capsys):
        (env.prompts / "default.txt").write_text("# comment\ndefault text\n")
        cmd = _dry_run(env, capsys, "-m", "m", "-s", "1")
        assert cmd[cmd.index("--prompt") + 1] == "default text"
        (env.prompts / "c.txt").write_text("cat")
        cmd = _dry_run(env, capsys, "-m", "m", "-s", "1", "-f", "c")
        assert cmd[cmd.index("--prompt") + 1] == "cat"

    def test_empty_negative_prompt_is_omitted(self, env, capsys):
        cmd = _dry_run(env, capsys, "-m", "m", "-p", "x", "-s", "1", "-n", "")
        assert "--negative-prompt" not in cmd


class TestMainErrors:
    def test_prompt_and_prompt_file_are_exclusive(self, env, capsys):
        with pytest.raises(SystemExit):
            env.main("-m", "m", "-p", "a", "-f", "b")
        assert "mutually exclusive" in capsys.readouterr().err

    def test_missing_model_dies(self, env, capsys):
        with pytest.raises(SystemExit):
            env.main("-p", "a", "--dry-run")
        assert "no model specified" in capsys.readouterr().err

    def test_missing_parameter_file_dies(self, env, capsys):
        with pytest.raises(SystemExit):
            env.main("-P", "nope", "-p", "a")
        assert "parameter file not found" in capsys.readouterr().err

    def test_cli_not_installed_dies(self, env, capsys):
        env.run.raise_not_found = True
        with pytest.raises(SystemExit) as exc:
            env.main("-m", "m", "-p", "a", "-s", "1")
        assert exc.value.code == 1
        assert "command not found: draw-things-cli" in capsys.readouterr().err

    def test_cli_failure_propagates_exit_code(self, env, capsys):
        env.run.returncode = 3
        with pytest.raises(SystemExit) as exc:
            env.main("-m", "m", "-p", "a", "-s", "1")
        assert exc.value.code == 3
        assert "writing output to" in capsys.readouterr().err

    def test_argparse_errors_exit_2(self, env, capsys):
        with pytest.raises(SystemExit) as exc:
            env.main("--enhance-language", "fr")
        assert exc.value.code == 2


class TestMainEnhance:
    def test_enhance_only_prints_and_stops(self, env, capsys, fake_enhancer, mod, monkeypatch):
        monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: False)
        instances = fake_enhancer("richer")
        env.main("-p", "plain", "--enhance-only")
        out, _ = capsys.readouterr()
        assert out == "richer\n"
        assert instances[0].calls == [("plain", mod.DEFAULT_PRESET, None)]
        assert env.run.commands == []

    def test_enhance_once_defaults_the_preset(self, env, capsys, fake_enhancer, mod):
        instances = fake_enhancer("richer")
        env.main("-m", "m", "-p", "plain", "-s", "1", "--enhance-once", "--dry-run")
        out, _ = capsys.readouterr()
        assert instances[0].calls == [("plain", mod.DEFAULT_PRESET, None)]
        assert shlex.split(out)[5] == "richer"

    def test_enhanced_text_gets_affixes(self, env, capsys, fake_enhancer, mod, monkeypatch):
        monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: False)
        (env.params / "p.toml").write_text(
            'model = "m"\nprompt_prefix = "pre"\n[enhancer]\nprovider = "x"\n')
        instances = fake_enhancer("richer")
        env.main("-P", "p", "-p", "plain", "-s", "1", "-e", "photo", "-L", "zh", "--dry-run")
        out, _ = capsys.readouterr()
        assert shlex.split(out)[5] == "pre, richer"
        assert instances[0].from_config_args == ("x", {}, "zh")
        assert instances[0].calls == [("plain", "photo", None)]

    def test_instruction_alone_enables_enhancement(self, env, capsys, fake_enhancer, mod,
                                                   monkeypatch):
        monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: False)
        instances = fake_enhancer("richer")
        env.main("-m", "m", "-p", "plain", "-s", "1", "-E", "bluer", "--dry-run")
        assert instances[0].calls == [("plain", None, "bluer")]


class TestMainGeneration:
    def test_embeds_metadata_into_generated_png(self, env, capsys):
        env.run.write = make_png(4, 4)
        (env.params / "p.toml").write_text('model = "m"\nsteps = 2\n[config]\nsampler = 1\n')
        env.main("-P", "p", "-p", "hello", "-n", "neg", "-s", "9")
        out = env.root / "1700000000-9.png"
        kinds = [k for k, _ in parse_chunks(out.read_bytes())]
        assert kinds == [b"IHDR", b"eXIf", b"iTXt", b"IDAT", b"IEND"]
        assert env.run.commands[0][-1] == str(out)
        assert capsys.readouterr().err == f"dtgen: writing output to {out}\n"

    def test_embed_metadata_false_skips(self, env):
        env.run.write = make_png()
        (env.params / "p.toml").write_text('model = "m"\nembed_metadata = false\n')
        env.main("-P", "p", "-p", "hello", "-s", "9")
        data = (env.root / "1700000000-9.png").read_bytes()
        assert data == make_png()

    def test_non_png_extension_skips(self, env):
        env.run.write = b"jpeg bytes"
        (env.params / "p.toml").write_text('model = "m"\noutput_ext = "jpg"\n')
        env.main("-P", "p", "-p", "hello", "-s", "9")
        assert (env.root / "1700000000-9.jpg").read_bytes() == b"jpeg bytes"

    def test_missing_output_warns(self, env, capsys):
        env.main("-m", "m", "-p", "hello", "-s", "9")
        assert "expected output not found, metadata not embedded" in capsys.readouterr().err

    def test_embedding_oserror_warns(self, env, capsys, mod, monkeypatch):
        env.run.write = make_png()

        def broken(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(mod, "embed_png_metadata", broken)
        env.main("-m", "m", "-p", "hello", "-s", "9")
        assert "failed to embed metadata: disk full" in capsys.readouterr().err


def test_real_subprocess_with_stub_cli(mod, tmp_path, monkeypatch, capsys):
    """End to end through subprocess.run against a stub draw-things-cli on PATH"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "stub.py"
    script.write_text(f"""import sys
argv = sys.argv[1:]
assert argv[0] == "generate", argv
open(argv[argv.index("--output") + 1], "wb").write({make_png(2, 2)!r})
""")
    # A shell wrapper keeps the interpreter path (which may contain spaces) out of the shebang
    stub = bin_dir / "draw-things-cli"
    stub.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} "$@"\n')
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod.time, "time", lambda: 1700000000)
    monkeypatch.setattr(sys, "argv", ["dtgen", "-m", "m", "-p", "hi", "-s", "3"])
    mod.main()
    out = tmp_path / "1700000000-3.png"
    kinds = [k for k, _ in parse_chunks(out.read_bytes())]
    assert b"iTXt" in kinds and b"eXIf" in kinds


def test_script_entry_point_runs_main(tmp_path, monkeypatch, capsys):
    """Executing the file as __main__ (as `uv run --script` does) reaches main()"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["dtgen", "-m", "m", "-p", "hi", "-s", "1", "--dry-run"])
    runpy.run_path(str(DTGEN_PATH), run_name="__main__")
    out = capsys.readouterr().out
    assert shlex.split(out)[:4] == ["draw-things-cli", "generate", "--model", "m"]
