# dtgen — draw-things-cli Wrapper

`dtgen` wraps `draw-things-cli generate`:
generation parameters are centralized in TOML files,
while the prompt and output path come from the command line.
See [MANUAL.md](MANUAL.md) for full usage;
this file only records what matters for development and maintenance.

## Architecture and Files

- `dtgen`: single-file Python 3 script (requires 3.11+, standard library only),
  meant to be symlinked into a directory on `PATH`;
  the script locates its real directory via `Path(__file__).resolve()`,
  so `parameters/` and `prompts/` always resolve relative to the tool's
  directory, never the cwd.
- `parameters/`: TOML parameter files.
  `example.toml` is a fully annotated template
  (including the complete sampler / seedMode enum tables);
  `default.toml` (text-to-image) and `i2i.toml` (image-to-image)
  are ready-to-use presets,
  and `t2i.toml` is the annotated version of `default.toml`.
- `prompts/`: prompt files, subdirectories supported
  (e.g. `prompts/negative/`).
  `default.txt` is the fallback when neither `--prompt` nor `--prompt-file`
  is given.
- `MANUAL.md`: the user manual.
  **It must be updated in sync whenever tool behavior changes**;
  the timestamp at the top must be obtained by actually running a command,
  and tables must be re-aligned after edits.

## Development and Testing

- Always verify argument assembly with `dtgen ... --dry-run`,
  which never triggers generation.
- For end-to-end tests, use reduced parameters (e.g. 448x448, steps 2)
  instead of running full-size defaults.
- Models live in the directory set by `[backend] models_dir`
  (or Draw Things' default location); make sure it is available before testing.
- PNGs produced by `draw-things-cli` carry no generation-parameter metadata;
  images produced by the Draw Things UI have an `eXIf` chunk plus an
  `iTXt` XMP block whose `exif:UserComment` `v2` member is the
  JSGenerationConfiguration JSON (usable as a reference sample).
  `dtgen` replicates that structure itself as a post-processing step
  after generation (see Metadata Embedding in MANUAL.md).

## Verified draw-things-cli Facts (do not override from memory; see sources below)

- How `--config-json` / `--config-file` merge:
  the dictionary is applied key by key onto the model's recommended-settings
  JSON, then decoded as `JSGenerationConfiguration`.
  It therefore only accepts the camelCase property names;
  **unknown keys are silently ignored**
  (aliases like `sampler_name` have no effect);
  enum fields (`sampler`, `seedMode`) only accept numbers —
  see `parameters/example.toml` for the value tables.
- `upscaler`, `refinerModel` and `faceRestoration` treat an empty string as
  disabled (the source explicitly says "Treat empty as nil");
  `colorCalibration` accepts `"none"` / `"lab"`.
- CLI setting precedence: command-line flags > config JSON >
  model recommended settings.
- An out-of-range enum value crashes the CLI outright
  (force-unwrap in the source), rather than producing an error message.
- A low-cost way to probe config key/value validity:
  add a nonexistent `--image` — if config parsing fails, the CLI reports
  `Failed to parse configuration override JSON` first;
  if parsing succeeds, it reports the missing input image instead —
  either way nothing is actually generated.
- Source (GitHub `drawthingsai/draw-things-community`):
  - `Apps/DrawThingsCLI/DrawThingsCLI.swift`:
    the CLI itself and the config merge logic
  - `Libraries/Scripting/Sources/ScriptModels.swift`:
    all `JSGenerationConfiguration` fields
  - `Libraries/DataModels/Sources/config.fbs`:
    the `SamplerType`, `SeedMode` and other enum definitions
