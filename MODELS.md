# Installed Draw Things Models

> Last updated: 2026-09-05T21:54:01+08:00

Inventory of the Draw Things official / community models installed in the models directory that the presets point to via `[backend] models_dir` (when the key is absent, `draw-things-cli` falls back to Draw Things' default location), together with the text encoders, VAEs and other files each of them depends on.\
Checkpoints and LoRAs imported from outside the Draw Things catalog are deliberately excluded.

Sources:

- `draw-things-cli models list --downloaded-only` for the model list and its official / community classification.
- Draw Things model catalog (`models.json`, `loras.json` cached under `~/Library/Containers/com.liuliu.draw-things/Data/Library/Caches/net/`) and the built-in `ModelZoo.swift` / `TextGenerationZoo.swift` / `LLMZoo.swift` of `drawthingsai/draw-things-community` for the dependency mapping.

## Models

| Model file                      | Name                          | Source    | Version      | Text encoder                     | Autoencoder (VAE)         | CLIP / vision encoder                | Preset                                                                     |
| ------------------------------- | ----------------------------- | --------- | ------------ | -------------------------------- | ------------------------- | ------------------------------------ | -------------------------------------------------------------------------- |
| `ernie_image_turbo_q6p.ckpt`    | ERNIE Image Turbo 1.0 (6-bit) | official  | `ernieImage` | `ministral_3_3b_q8p.ckpt`        | `flux_2_vae_f16.ckpt`     | -                                    | `parameters/t2i/ernie/dist.toml`                                           |
| `z_image_turbo_1.0_q8p.ckpt`    | Z Image Turbo 1.0             | official  | `zImage`     | `qwen_3_vl_4b_instruct_q8p.ckpt` | `flux_1_vae_f16.ckpt`     | -                                    | `parameters/t2i/z-image-turbo/dist.toml`                                   |
| `z_image_1.0_q8p.ckpt`          | Z Image Base 1.0              | official  | `zImage`     | `qwen_3_vl_4b_instruct_q8p.ckpt` | `flux_1_vae_f16.ckpt`     | -                                    | -                                                                          |
| `qwen_image_2512_q6p.ckpt`      | Qwen Image 2512 (6-bit)       | official  | `qwenImage`  | `qwen_2.5_vl_7b_q8p.ckpt`        | `qwen_image_vae_f16.ckpt` | -                                    | `parameters/t2i/qwen-2512/dist.toml`, `parameters/t2i/qwen-2512/wuli.toml` |
| `qwen_image_edit_2511_q6p.ckpt` | Qwen Image Edit 2511 (6-bit)  | official  | `qwenImage`  | `qwen_2.5_vl_7b_q8p.ckpt`        | `qwen_image_vae_f16.ckpt` | `qwen_2.5_vl_7b_vit_f16.ckpt`        | `parameters/i2i/qwen-2511/dist.toml`                                       |
| `flux_2_klein_9b_q6p.ckpt`      | FLUX.2 [klein] 9B (6-bit)     | official  | `flux2_9b`   | `qwen_3_8b_q8p.ckpt`             | `flux_2_vae_f16.ckpt`     | -                                    | `parameters/t2i/flux-2-klein-9b/dist.toml`                                 |
| `krea_2_turbo_q8p.ckpt`         | Krea 2 Turbo                  | community | `krea_2`     | `qwen_3_vl_4b_q8p.ckpt`          | `qwen_image_vae_f16.ckpt` | itself (`clip_encoder` = model file) | `parameters/t2i/krea-2-turbo/dist.toml`                                    |

Notes:

- `krea_2_turbo_q8p.ckpt` is listed as `community` by `draw-things-cli models list --downloaded-only` because the catalog entry is served from `models.json` rather than being built into the CLI binary;\
  the same catalog marks it as an official Draw Things conversion (`© 2026 Krea.ai, Inc.`).
- None of the installed models declares a refiner;\
  `refinerModel` stays `""` in every preset.

## Dependencies

| File                                               | Kind              | Used by                                             |
| -------------------------------------------------- | ----------------- | --------------------------------------------------- |
| `ministral_3_3b_q8p.ckpt` (+ `-tensordata`)        | Text encoder      | ERNIE Image Turbo 1.0                               |
| `qwen_3_vl_4b_instruct_q8p.ckpt` (+ `-tensordata`) | Text encoder      | Z Image Turbo 1.0, Z Image Base 1.0                 |
| `qwen_3_vl_4b_q8p.ckpt`                            | Text encoder      | Krea 2 Turbo                                        |
| `qwen_3_8b_q8p.ckpt` (+ `-tensordata`)             | Text encoder      | FLUX.2 [klein] 9B                                   |
| `qwen_2.5_vl_7b_q8p.ckpt` (+ `-tensordata`)        | Text encoder      | Qwen Image 2512, Qwen Image Edit 2511               |
| `qwen_2.5_vl_7b_vit_f16.ckpt`                      | Vision encoder    | Qwen Image Edit 2511 (reference-image conditioning) |
| `flux_1_vae_f16.ckpt`                              | Autoencoder (VAE) | Z Image Turbo 1.0, Z Image Base 1.0                 |
| `flux_2_vae_f16.ckpt`                              | Autoencoder (VAE) | ERNIE Image Turbo 1.0, FLUX.2 [klein] 9B            |
| `qwen_image_vae_f16.ckpt`                          | Autoencoder (VAE) | Qwen Image 2512, Qwen Image Edit 2511, Krea 2 Turbo |

## Official LoRAs

| LoRA file                                             | Name                                  | Version      | Preset                               |
| ----------------------------------------------------- | ------------------------------------- | ------------ | ------------------------------------ |
| `qwen_image_2512_lightning_4_step_v1.0_lora_f16.ckpt` | Qwen Image 2512 Lightning 4-Step v1.0 | `qwen_image` | `parameters/t2i/qwen-2512/dist.toml` |
| `qwen_image_2512_turbo_4_step_v1.0_lora_f16.ckpt`     | Qwen Image 2512 Turbo 4-Step v1.0     | `qwen_image` | -                                    |

Both LoRAs come from the Draw Things `loras.json` catalog.

## Other Draw Things Files

| File                                     | Kind                                   | Note                                                                                              |
| ---------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `qwen_3.5_4b_i8x.ckpt` (+ `-tensordata`) | Built-in LLM (Qwen 3.5 4B VL, 8-bit S) | Used by Draw Things' own text-generation / prompt features, not by any installed diffusion model. |
| `clip_vit_l14_f16.ckpt`                  | CLIP ViT-L/14 text encoder             | Shared dependency of SD 1.x / Chroma / FLUX.1-family catalog models; no installed model needs it. |
