Add-Type -AssemblyName PresentationCore

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'output\test_walk_se'
$output = Join-Path $root 'output\gait_previews'
New-Item -ItemType Directory -Force -Path $output | Out-Null

@{
    'preset_a_125ms.gif' = 13
    'preset_b_150ms.gif' = 15
    'preset_c_175ms.gif' = 18
}.GetEnumerator() | ForEach-Object {
    $fileName = $_.Key
    $delay = $_.Value
    $encoder = [System.Windows.Media.Imaging.GifBitmapEncoder]::new()
    0..3 | ForEach-Object {
        $uri = [Uri](Join-Path $source ('frame_{0:D2}.png' -f $_))
        $metadata = [System.Windows.Media.Imaging.BitmapMetadata]::new('gif')
        $metadata.SetQuery('/grctlext/Delay', [uint16]$delay)
        $metadata.SetQuery('/grctlext/Disposal', [byte]2)
        $frame = [System.Windows.Media.Imaging.BitmapFrame]::Create($uri, [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat,
            [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
        $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($frame, $frame.Thumbnail, $metadata, $frame.ColorContexts))
    }
    $stream = [System.IO.File]::Open((Join-Path $output $fileName), [System.IO.FileMode]::Create)
    $encoder.Save($stream)
    $stream.Dispose()
}

Write-Output 'GAIT_PREVIEWS=125,150,175MS'
