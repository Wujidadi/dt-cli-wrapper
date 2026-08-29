# dtgen User Manual

> Last updated: 2026-08-30T03:12:01+08:00

`dtgen` is a wrapper for `draw-things-cli generate`:
generation parameters are centralized in TOML files,
the prompt and output path come from the command line,
and everything else (model resolution, recommended settings, the actual generation)
is left to `draw-things-cli`.

## Installation and Directory Layout

- The tool itself is `dtgen` in this directory
  (single-file Python 3 script, zero external dependencies, requires Python 3.11+).
- Symlink it into any directory on your `PATH` to run it from anywhere;
  the script resolves the symlink by itself,
  so `parameters/` and `prompts/` always resolve to the tool's real directory.

```
dt-cli-wrapper/
├── dtgen                  # The tool itself
├── parameters/            # Parameter files (TOML)
│   └── example.toml       # Fully annotated example
├── prompts/               # Prompt files
│   └── default.txt        # Optional; final fallback when no prompt is given
└── enhancers/             # Prompt-enhancement presets (see Prompt Enhancement)
    └── ernie.txt          # Default preset
```

## Basic Usage

```sh
# Generate with the parameters in parameters/example.toml,
# output to the current directory
dtgen -P example -p "a red cube on a table"

# No parameter file: the model's recommended settings apply,
# and the model must be given via --model
dtgen -m flux_2_klein_4b_q6p.ckpt -p "a red cube on a table"

# Prompt from prompts/cube.txt, output into a directory
# (created automatically when missing, file auto-named)
dtgen -P example --prompt-file cube -o ~/Pictures/dt

# Image-to-image: -i sets the input image; denoising strength and related
# parameters live in the parameter file (e.g. strength in parameters/i2i.toml)
dtgen -P i2i -i input.png -p "studio portrait"

# Enhance the prompt with a local ollama model before generating
# (interactive: review the result, then generate, re-enhance, or quit)
dtgen -P example -p "一隻橘貓在窗台上睡覺" --enhance

# Enhance with a specific preset, or apply an ad-hoc instruction only
dtgen -P example -p "a fox in snow" -e ghibli-watercolor
dtgen -P example -p "a girl on a beach" -E "add a straw hat"

# Print the enhanced prompt and exit without generating
dtgen -p "a fox in snow" --enhance-only

# Extra options after "--" are passed through to draw-things-cli
dtgen -P example -p "test" -- --terminal-image

# Print the full command that would run, without executing it
dtgen -P example -p "test" --dry-run
```

## Command-Line Options

| Option                   | Short | Description                                                    |
| ------------------------ | ----- | -------------------------------------------------------------- |
| `--parameter-file <f>`   | `-P`  | Parameter file                                                 |
| `--prompt <text>`        | `-p`  | Prompt text                                                    |
| `--prompt-file <f>`      | `-f`  | Prompt file                                                    |
| `--negative-prompt <t>`  | `-n`  | Negative prompt text                                           |
| `--negative-prompt-file` | `-N`  | Negative prompt file                                           |
| `--image <path>`         | `-i`  | Input image for img2img                                        |
| `--enhance [<preset>]`   | `-e`  | Enhance the prompt via local ollama; preset defaults to ernie  |
| `--enhance-instruction`  | `-E`  | Ad-hoc enhancement instruction; alone it means custom mode     |
| `--enhance-once`         |       | Enhance once and generate directly, no interactive loop        |
| `--enhance-only`         |       | Print the enhanced prompt to stdout, skip generation           |
| `--model <model>`        | `-m`  | Model; overrides the parameter file; required without one      |
| `--seed <n>`             | `-s`  | Random seed; overrides the parameter file; random when omitted |
| `--output <dir>`         | `-o`  | Output directory; created when missing; default: current dir   |
| `--dry-run`              |       | Print the command without executing it                         |
| Arguments after `--`     |       | Passed through to `draw-things-cli generate` verbatim          |

## Name Resolution Rules

`--parameter-file` and `--prompt-file` (including `--negative-prompt-file`)
share the same rules:

- Values starting with `/`, `~`, `./` or `../` are treated as plain paths
  (absolute, or relative to the current working directory).
- Anything else is a name under `parameters/` or `prompts/`,
  subdirectories allowed:
  - When the last segment has no extension,
    the default extension (`.toml` / `.txt`) is appended —
    `-P example` means `parameters/example.toml`,
    `-P zimage/portrait` means `parameters/zimage/portrait.toml`.
  - When the last segment has an extension, it is used as-is —
    `--prompt-file foo.md` means `prompts/foo.md`
    (prompt files are not limited to `.txt`).

## Prompt Resolution Order

1. `--prompt` (mutually exclusive with `--prompt-file`; giving both is an error)
2. `--prompt-file`
3. `prompt` in the parameter file
4. `prompts/default.txt`
5. Error when none of the above exists

`prompt_prefix` / `prompt_suffix` from the parameter file are joined to the final
prompt with `, ` — a suitable place for LoRA trigger words or fixed quality terms.
The negative prompt follows the same order (command line over parameter file);
when neither provides one, the model's recommended value applies.

### Prompt File Format

- Any extension is accepted (`.txt`, `.md`, ...); the whole file is the prompt,
  with line breaks and blank lines preserved as-is.
- Lines starting with `# ` or `// ` (leading whitespace allowed;
  a line consisting solely of `#` or `//` also counts) are comments
  and are dropped entirely; `#` without a following space (e.g. `#tag`)
  is not a comment.
  Only full-line comments are supported; trailing comments are not.
- After filtering comments, leading and trailing whitespace is stripped
  to produce the final prompt; negative prompt files and
  `prompts/default.txt` follow the same rules.

## Prompt Enhancement

`--enhance` / `--enhance-instruction` rewrite the prompt with a local LLM
served by [ollama](https://ollama.com) before generation,
porting the "prompt-enhancer" script workflow from the Draw Things UI.
Requirements: a running ollama service and a pulled model
(defaults: `http://localhost:11434`, `qwen3.5:4b`;
override via the `[enhancer]` section of the parameter file).
The model's thinking mode is always disabled,
and the enhanced prompt is always written in English,
regardless of the input language.

### Modes

- `--enhance [<preset>]` — preset mode.
  The optional value names a preset under `enhancers/`
  (same resolution rules as `--prompt-file`, default extension `.txt`);
  when omitted, `ernie` is used.
  A preset file is the complete system instruction sent to the model;
  edit or add files there to customize.
- `--enhance-instruction <text>` — with `--enhance`,
  the text is appended to the preset as an overriding requirement;
  alone, it enables custom mode:
  a rewrite that merges the instruction into the original prompt
  (e.g. "add a straw hat") while keeping everything else intact.

### Interactive Loop

When stdin is a terminal (and `--enhance-only` is not given),
each enhancement round prints the result and asks for the next action:

- `g` — generate with the current enhanced prompt
- `e` — feed the enhanced prompt back for another enhancement round
- `i` — enter a new ad-hoc instruction, then re-enhance
- `q` — quit without generating (exit status 0)

When stdin is not a terminal, or `--enhance-once` is given,
a single enhancement pass runs and generation proceeds directly.

### Notes on Behavior

- `--enhance-only` prints the final enhanced prompt to stdout and exits;
  no model, parameter file, or output path is required.
  It and `--enhance-once` both imply the default preset
  when neither `--enhance` nor `--enhance-instruction` is given.
- The prompt being enhanced may come from any source in the resolution order:
  `--prompt`, `--prompt-file`, the parameter file's `prompt`,
  or `prompts/default.txt`.
- Enhancement applies to the bare prompt;
  `prompt_prefix` / `prompt_suffix` are joined afterwards,
  so LoRA trigger words are never rewritten by the enhancer.
  The negative prompt is never touched.
- Markdown code fences and wrapping quotes are stripped from the model output
  (some presets, e.g. `ernie`, ask the model to answer in a code block).
- `--dry-run` still performs the enhancement
  (it is a real ollama call, but never triggers image generation),
  so the printed command shows the actual final prompt.

### Bundled Presets

| Preset                | Type    | Description                                  |
| --------------------- | ------- | -------------------------------------------- |
| `ernie`               | General | Detailed objective image description         |
| `z-image`             | General | Faithful, aesthetic visual description       |
| `anima`               | Model   | Anima tag-format prompt rules                |
| `ltx-video`           | Model   | LTX-2.3 audio-video cinematic prompt         |
| `leica-portrait`      | Style   | Cinematic photorealistic portrait            |
| `ghibli-watercolor`   | Style   | Studio Ghibli watercolor painting            |
| `cyberpunk-mecha`     | Style   | Futuristic cyberpunk concept art             |
| `monet-impressionist` | Style   | Monet-like Impressionist oil painting        |
| `vaporwave-surreal`   | Style   | Vaporwave retro-futurism aesthetic           |
| `space-epic`          | Style   | Sci-fi space art with epic scale             |
| `chinoiserie-ink`     | Style   | Modern Chinese splash-ink style              |
| `vinyl-toy`           | Style   | Cute 3D Pop Mart vinyl toy style             |
| `wabi-sabi-minimal`   | Style   | Wabi-sabi architectural minimalism           |

## Seed and Output File Name

- Seed precedence: `--seed` > `seed` in the parameter file > randomly generated.
  A randomly generated seed is still passed to `draw-things-cli` explicitly,
  so results are always reproducible.
- `--output` is always treated as a directory;
  when it does not exist, it is created recursively (like `mkdir -p`).
  The file is always auto-named `<unix seconds>-<seed>.<ext>`,
  e.g. `1787847667-42.png`, so the seed survives in the file name
  even without the embedded metadata (see Metadata Embedding).
  There is no custom file-name option;
  rename afterwards with your own script if needed.
- The auto-naming extension comes from `output_ext` in the parameter file,
  defaulting to `png`; set it to `mp4` or `mov` for video models.
- Before running, the actual output path is printed to stderr
  (`dtgen: writing output to ...`).

## Metadata Embedding

`draw-things-cli` writes bare pixels only,
so `dtgen` embeds generation metadata into the output PNG itself
after a successful run,
replicating the structure the Draw Things UI writes:

- an `eXIf` chunk carrying the pixel dimensions;
- an `iTXt` XMP block containing:
  - `dc:description` — the prompt,
    the negative prompt on a `-`-prefixed line,
    and a human-readable parameter summary line
    (`Steps: ..., Sampler: ..., Seed: ..., Size: ..., Model: ...`);
  - `xmp:CreatorTool` — `Draw Things`;
  - `exif:UserComment` — a JSON object whose `v2` member is the
    `JSGenerationConfiguration` dictionary,
    the same format the UI embeds and can read back.

Only parameters known to `dtgen` are written:
the parameter file's values plus command-line overrides,
with the actual size taken from the generated PNG header.
Model recommended settings that `dtgen` never saw are not included,
and arguments passed through after `--` are not reflected.
Set `embed_metadata = false` in the parameter file to disable embedding;
non-PNG outputs (`mp4`, `mov`) are always skipped.

## Parameter Files (TOML)

All keys are optional; anything omitted falls back to Draw Things'
recommended settings for the model.
The only exception is `model` —
it must be provided either in the file or via `--model`.
Unknown keys produce a warning on stderr and are ignored,
so a typo never fails silently.

### Top-Level Keys

| Key               | Type    | Description                                   |
| ----------------- | ------- | --------------------------------------------- |
| `model`           | string  | Model file name, display name, hf ref, HF URL |
| `prompt`          | string  | Default prompt                                |
| `negative_prompt` | string  | Default negative prompt                       |
| `prompt_prefix`   | string  | Joined before the final prompt                |
| `prompt_suffix`   | string  | Joined after the final prompt                 |
| `output_ext`      | string  | Auto-naming extension, default png            |
| `steps`           | integer | Sampling steps                                |
| `cfg`             | number  | CFG guidance scale                            |
| `width`           | integer | Output width, multiple of 64                  |
| `height`          | integer | Output height, multiple of 64                 |
| `frames`          | integer | Frame count for video models                  |
| `strength`        | number  | img2img denoising strength, 0 to 1            |
| `seed`            | integer | Fixed seed                                    |
| `embed_metadata`  | boolean | Embed XMP metadata into PNG, default true     |

### `[config]` — Advanced Overrides

This table is converted to JSON verbatim and passed to `draw-things-cli`
via `--config-json` (`JSGenerationConfiguration` format,
merged onto the model's recommended settings).
It covers what the command-line flags do not:
sampler, shift, hires fix, LoRA, and so on.
Key names follow `JSGenerationConfiguration`; the tool does no translation.

```toml
[config]
sampler = 12

# Local LoRAs not registered in custom_lora.json need a version (e.g. "flux1")
[[config.loras]]
file = "my_lora_f16.ckpt"
weight = 0.8
version = "flux1"
```

### `[enhancer]` — Prompt Enhancement Backend

Defaults apply when omitted (see Prompt Enhancement).

| Key     | Type   | Description                                        |
| ------- | ------ | -------------------------------------------------- |
| `url`   | string | ollama endpoint, default `http://localhost:11434`  |
| `model` | string | ollama model name, default `qwen3.5:4b`            |

### `[backend]` — Execution Backend

Local generation by default when omitted.

| Key                    | Type    | Flag                             |
| ---------------------- | ------- | -------------------------------- |
| `cloud_compute`        | boolean | `--cloud-compute`                |
| `remote`               | boolean | `--remote`                       |
| `remote_url`           | string  | `--remote-url`                   |
| `remote_port`          | integer | `--remote-port`                  |
| `remote_tls`           | boolean | `--remote-tls` `--no-remote-tls` |
| `remote_shared_secret` | string  | `--remote-shared-secret`         |
| `api_key`              | string  | `--api-key`                      |
| `cloud_api_base_url`   | string  | `--cloud-api-base-url`           |
| `models_dir`           | string  | `--models-dir`                   |

### `[options]` — Other Execution Options

| Key                | Type    | Flag                                         |
| ------------------ | ------- | -------------------------------------------- |
| `download_missing` | boolean | `--download-missing` `--no-download-missing` |
| `disable_preview`  | boolean | `--disable-preview`                          |
| `offline`          | boolean | `--offline`                                  |

## Notes

- Images written by `draw-things-cli` itself carry no generation metadata;
  the XMP block found in `dtgen` output is embedded by `dtgen`
  as a post-processing step (see Metadata Embedding).
  The auto-named output file preserves the seed even when embedding
  is disabled or fails.
- `dtgen` always passes `--output`,
  so `draw-things-cli`'s native behavior of
  "terminal preview only, no file written, when `--output` is omitted"
  never occurs; to preview in the terminal, pass through `-- --terminal-image`.
- On a parse failure, a missing file, or a missing model or prompt,
  the tool exits with a non-zero status and explains why on stderr.
- New `draw-things-cli` options not covered by the parameter file sections
  can always be passed through after `--`, with no tool changes needed.
