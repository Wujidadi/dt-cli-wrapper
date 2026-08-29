# dtgen User Manual

> Last updated: 2026-08-30T00:19:25+08:00

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
└── prompts/               # Prompt files
    └── default.txt        # Optional; final fallback when no prompt is given
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
