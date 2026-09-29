# CH Audio Lab V1

`CH Audio Lab` is the City Horizon generative-audio pipeline.

It deliberately separates **generation** from **runtime mastering**:

```text
AI prompt / source
      ↓
CH_AUDIO_GENERATION_V1
      ↓
provider
      ↓
master audio
      ↓
audio_asset_worker.py
      ↓
OGG/Vorbis 48 kHz + validation report
      ↓
review artifact or runtime catalog promotion
```

## Contracts

### `CH_AUDIO_GENERATION_V1`

A generation request. Required fields:

- `contract`: `CH_AUDIO_GENERATION_V1`
- `id`: stable job identifier
- `kind`: `effect`, `ambient`, or `music`
- `prompt`: natural-language generation instruction
- `durationSeconds`: requested duration, up to 600 seconds
- `provider`: generation provider configuration

Optional fields include `negativePrompt`, `tags`, `mastering`, `outputDir`, and `target`.

### `CH_AUDIO_ASSET_REPORT_V1`

Produced by `tools/audio_asset_worker.py`. It records codec, sample rate, channel count, duration, SHA-256 hashes and mastering settings.

### `CH_AUDIO_LAB_REPORT_V1`

Produced by `tools/ch_audio_lab/ch_audio_lab.py`. It links the original prompt, provider proof, generated master, review/runtime OGG and asset validation report.

## Providers

### `synthetic_smoke`

Deterministic built-in generator used to validate the pipeline without external credentials. It is **not** intended to replace a production generative-audio model.

Profiles currently available:

- `ui_click`
- `steam_hiss`
- `mechanical_loop`
- `rain`
- `thunder`
- `ambient_pad`

### `source`

Copies an existing source file into the lab workspace and sends it through the same mastering/validation path.

```json
{
  "provider": {
    "type": "source",
    "source": "Converter/example.wav"
  }
}
```

### `command`

Stable integration seam for a real AI audio generator. The command is executed without a shell. Secrets must come from the environment, never from the JSON job.

Supported placeholders:

- `{prompt}`
- `{prompt_file}`
- `{output}`
- `{duration}`
- `{repo}`

Example:

```json
{
  "provider": {
    "type": "command",
    "command": [
      "python",
      "tools/my_audio_provider.py",
      "--prompt-file", "{prompt_file}",
      "--duration", "{duration}",
      "--output", "{output}"
    ]
  }
}
```

A provider wrapper may call a hosted model/API or a local model such as MusicGen/AudioCraft. The CH Audio Lab contract does not depend on one vendor.

## Review first, promote second

Generated audio should normally use:

```json
{
  "target": {
    "register": false
  }
}
```

This creates review artifacts without changing `assets/audio/audio_catalog.json`.

After approval, a job may target a path under `assets/audio/` and set `register: true`, with either:

- `event` for `effect` / `ambient`; or
- `slot` for `music`.

Existing legacy jobs in `tools/audio_jobs/` remain supported by `audio_asset_worker.py`.

## Mastering defaults

Runtime/review OGG files are always 48 kHz Vorbis. Defaults:

| Kind | Channels | Vorbis quality | Default target when normalization is enabled |
|---|---:|---:|---:|
| effect | mono | 4 | -18 LUFS |
| ambient | stereo | 5 | -20 LUFS |
| music | stereo | 5 | -16 LUFS |

Normalization is opt-in. Jobs can override channel count, quality, LUFS, true peak and fades.

## Local usage

```bash
python tools/ch_audio_lab/ch_audio_lab.py tools/ch_audio_lab/jobs/steam_hiss_smoke.json
```

The default output goes to `out/ch-audio-lab/<job-id>/` and contains:

```text
generation_request.json
master.wav
asset_job_resolved.json
asset_report.json
review.ogg
audio_lab_report.json
```

The GitHub Actions workflow `CH Audio Lab` runs explicit jobs and uploads the complete review package as an artifact.
