# Draw Things CLI Generate Wrapper

`dtgen` is a wrapper for [draw-things-cli](https://docs.drawthings.ai/) `generate`:
generation parameters are centralized in TOML files,
while the prompt and output path come from the command line —
switching models or scenarios becomes a matter of switching a file name.

## Features

- TOML parameter files: common sampling parameters go in top-level keys,
  advanced items (sampler, LoRA, backend, ...) go in `[config]`
  and are passed through verbatim as `--config-json`;
  when no parameter file is given, Draw Things'
  per-model recommended settings apply.
- Prompts and negative prompts can be managed as files:
  subdirectories, arbitrary extensions, `# ` / `// ` full-line comments,
  and multi-line content are all supported.
- Outputs are auto-named `<unix timestamp>-<seed>.<ext>`;
  when no seed is given, one is generated randomly and passed explicitly,
  so every result is reproducible.
- Optional prompt enhancement via a local ollama model (`--enhance`):
  preset-driven or ad-hoc-instruction rewriting with an interactive
  review loop, ported from the Draw Things UI "prompt enhancer" script.
- `--dry-run` previews the full command;
  arguments after `--` are passed through to `draw-things-cli` verbatim.

## Requirements

- macOS with `draw-things-cli` installed
  (available in homebrew-core: `brew install draw-things-cli`)
- Python 3.11+ (standard library only)
- Draw Things model files
  (the path can be set via `[backend] models_dir` in a parameter file)
- For prompt enhancement only: a running [ollama](https://ollama.com)
  service with a pulled model (default `qwen3.5:4b`, about 3.4 GB);
  everything else works without it

## Installation

Symlink `dtgen` into any directory on your `PATH`, for example:

```sh
ln -s "$PWD/dtgen" ~/.local/bin/dtgen
```

The tool resolves the symlink back to this directory by itself,
so `parameters/` and `prompts/` are unaffected by where it is run from.

## Quick Start

```sh
# Generate with the parameters in parameters/default.toml
# and the prompt in prompts/default.txt
dtgen -P default

# Different prompt, output to a specific directory
dtgen -P default -p "a red cube on a table" -o ~/Pictures/dt/

# Image-to-image (denoising strength and related parameters live in parameters/i2i.toml)
dtgen -P i2i -i input.png

# No parameter file: the model's recommended settings apply,
# and the model must be given via --model
dtgen -m flux_2_klein_4b_q6p.ckpt -p "a red cube on a table"

# Enhance the prompt with a local ollama model, review, then generate
dtgen -P default -p "一隻橘貓在窗台上睡覺" --enhance
```

## Directory Layout

```
dt-cli-wrapper/
├── dtgen                  # The tool itself (single-file Python 3 script)
├── parameters/            # TOML parameter files (example.toml is an annotated template)
├── prompts/               # Prompt files (default.txt is the fallback prompt)
├── enhancers/             # Prompt-enhancement presets (ernie.txt is the default)
├── MANUAL.md              # Full user manual
└── AGENTS.md              # Development notes (imported by CLAUDE.md)
```

## Documentation

- [MANUAL.md](MANUAL.md): command-line options, name resolution rules,
  and the full parameter file reference
- [AGENTS.md](AGENTS.md): development and maintenance notes,
  including verified `draw-things-cli` behavior details
