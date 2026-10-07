# CH Audio Lab inbox

Place original recordings here when you want CH Audio Lab to clean/master them.

Recommended source: WAV, preferably 48 kHz and 24-bit when available. Short
MP3/M4A/OGG sources can also be decoded by FFmpeg, but keeping the original WAV
is better for sale/archive quality.

Do not overwrite the raw recording after review. A source-provider job copies
the file into its review artifact and, when recorded-SFX cleanup is enabled,
creates a separate `clean_master.wav`.

Create a job from `tools/ch_audio_lab/examples/recorded_sfx_cleanup.json`,
point `provider.source` at the recording, and keep `target.register=false`
until the processed sound has been reviewed.
