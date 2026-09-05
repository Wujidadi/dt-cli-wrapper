# dtgen — draw-things-cli Wrapper

`dtgen` wraps `draw-things-cli generate`:\
generation parameters are centralized in TOML files, while the prompt and output path come from the command line.\
See [MANUAL.md](MANUAL.md) for full usage;\
this file only records what matters for development and maintenance.

## Architecture and Files

- `dtgen`: single-file Python 3 script (requires 3.11+), meant to be symlinked into a directory on `PATH`.\
  Its shebang is `uv run --script`, and its only dependency is `text-to-image-prompt-enhancer` (GitHub `Wujidadi/text-to-image-prompt-enhancer`, local checkout at `~/Documents/Workspaces/AI/Text-to-image/prompt-enhancer`), declared as PEP 723 inline metadata pinned to a release tag;\
  bump the tag there when the package changes.\
  The script locates its real directory via `Path(__file__).resolve()`, so `parameters/` and `prompts/` always resolve relative to the tool's directory, never the cwd.
- `parameters/`: TOML parameter files.\
  `example.toml` is a fully annotated template (including the complete sampler / seedMode enum tables);\
  `default.toml` (text-to-image) and `i2i.toml` (image-to-image) are ready-to-use presets;\
  `t2i.toml` is the annotated version of `default.toml`.
- `prompts/`: prompt files, subdirectories supported (e.g. `prompts/negative/`).\
  `default.txt` is the fallback when neither `--prompt` nor `--prompt-file` is given.
- Prompt enhancement (`--enhance` / `--enhance-instruction`):\
  presets, language directives, the Traditional-to-Simplified pass, output cleanup and the provider backends all live in the `text-to-image-prompt-enhancer` package (`prompt_enhancer` module);\
  `dtgen` keeps only the interactive review loop and maps the parameter file's `[enhancer]` section onto `Enhancer.from_config(provider, overrides, language=...)`.\
  Change enhancement behavior in that package, not here.
- `MANUAL.md`: the user manual.\
  **It must be updated in sync whenever tool behavior changes**;\
  the timestamp at the top must be obtained by actually running a command, and tables must be re-aligned after edits.

## Development and Testing

- Always verify argument assembly with `dtgen ... --dry-run`, which never triggers generation (with `--enhance` it still calls the model for the enhancement itself).
- Until the dependency's git tag is published, or to test against a local checkout of the package, bypass the inline metadata with `uv run --no-project --with <package dir> python dtgen ...`.
- The editor (Pylance) resolves imports from `.venv/` (gitignored), created with `uv venv --python 3.11 .venv` and `uv pip install --python .venv -e <package dir>`;\
  the runtime never uses that venv, `uv run --script` builds its own environment from the inline metadata.
- Unit tests live in `tests/` (pytest);\
  `tests/conftest.py` loads the extensionless `dtgen` file as a module through `SourceFileLoader`, so tests import it as `dtgen`.\
  Run them with the editor venv, which also carries `pytest` and `pytest-cov` (`uv pip install --python .venv pytest pytest-cov`):

  ```sh
  .venv/bin/python -m pytest --cov
  ```

  Coverage settings (`source`, branch mode) live in `pyproject.toml`, which holds tool configuration only and no `[project]` table;\
  the suite is expected to keep `dtgen` at 100% line and branch coverage, and touches neither the network nor a real `draw-things-cli`.
- `dtgen -p "..." --enhance-only` exercises the enhancement path alone:\
  no model, parameter file, or output involved.
- For end-to-end tests, use reduced parameters (e.g. 448x448, steps 2) instead of running full-size defaults.
- Models live in the directory set by `[backend] models_dir` (or Draw Things' default location);\
  make sure it is available before testing.
- PNGs produced by `draw-things-cli` carry no generation-parameter metadata;\
  images produced by the Draw Things UI have an `eXIf` chunk plus an `iTXt` XMP block whose `exif:UserComment` `v2` member is the JSGenerationConfiguration JSON (usable as a reference sample).\
  `dtgen` replicates that structure itself as a post-processing step after generation (see Metadata Embedding in MANUAL.md).

## Verified draw-things-cli Facts (do not override from memory; see sources below)

- How `--config-json` / `--config-file` merge:\
  the dictionary is applied key by key onto the model's recommended-settings JSON, then decoded as `JSGenerationConfiguration`.\
  It therefore only accepts the camelCase property names;\
  **unknown keys are silently ignored** (aliases like `sampler_name` have no effect);\
  enum fields (`sampler`, `seedMode`) only accept numbers —\
  see `parameters/example.toml` for the value tables.
- `upscaler`, `refinerModel` and `faceRestoration` treat an empty string as disabled (the source explicitly says "Treat empty as nil");\
  `colorCalibration` accepts `"none"` / `"lab"`.
- CLI setting precedence: command-line flags > config JSON > model recommended settings.
- An out-of-range enum value crashes the CLI outright (force-unwrap in the source), rather than producing an error message.
- A low-cost way to probe config key/value validity:\
  add a nonexistent `--image` —\
  if config parsing fails, the CLI reports `Failed to parse configuration override JSON` first;\
  if parsing succeeds, it reports the missing input image instead —\
  either way nothing is actually generated.
- Source (GitHub `drawthingsai/draw-things-community`):
  - `Apps/DrawThingsCLI/DrawThingsCLI.swift`: the CLI itself and the config merge logic
  - `Libraries/Scripting/Sources/ScriptModels.swift`: all `JSGenerationConfiguration` fields
  - `Libraries/DataModels/Sources/config.fbs`: the `SamplerType`, `SeedMode` and other enum definitions

## Conventions

- Everything in this repository is written in English:\
  code, comments, documentation, commit messages.
- Markdown prose is wrapped by meaning, not by column width:
  - one sentence per line, however long;\
    break only at a sentence end, at a semicolon joining two substantial clauses, or at a colon or dash that introduces a clause or list;
  - never break after a comma, unless a single sentence is long enough to span three or four displayed lines;
  - inside a paragraph or a list item, every line except the last ends with a `\` hard break, so GitHub renders the line breaks instead of collapsing them into spaces;
  - a comma-separated enumeration with long or many items becomes a Markdown list;
  - tables and code blocks are left as they are;\
    re-align tables by display width after editing (CJK characters count as two columns).
- `MANUAL.md` and `MODELS.md` carry a `Last updated` ISO 8601 timestamp at the top, obtained by actually running a command, never estimated.
- Documents describe the current state only;\
  history belongs to Git, not to the documents.
