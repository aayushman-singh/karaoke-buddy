$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$exe = Join-Path $root "build/dist/KaraokeBuddy.exe"
$screenshot = Join-Path $root "docs/packaged-home.png"

python (Join-Path $root "build/build.py")

if (!(Test-Path $exe)) {
    throw "Packaged exe was not created at $exe"
}

Get-Process KaraokeBuddy -ErrorAction SilentlyContinue | Stop-Process -Force

$launcher = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -PassThru
$visible = $null

for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    $visible = Get-Process KaraokeBuddy -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq "KaraokeBuddy" -and $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1
    if ($visible) {
        break
    }
    $launcher.Refresh()
    if ($launcher.HasExited) {
        throw "KaraokeBuddy exited with code $($launcher.ExitCode) before the home window appeared."
    }
}

if (-not $visible) {
    throw "No visible KaraokeBuddy home window appeared within 90 seconds."
}

$captureApi = @"
using System;
using System.Runtime.InteropServices;
public class PackagedHomeCapture {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
}
"@
Add-Type $captureApi -ErrorAction SilentlyContinue

$handle = $visible.MainWindowHandle
[PackagedHomeCapture]::MoveWindow($handle, 120, 80, 1000, 720, $true) | Out-Null
Start-Sleep -Milliseconds 600

$rect = New-Object PackagedHomeCapture+RECT
[PackagedHomeCapture]::GetWindowRect($handle, [ref]$rect) | Out-Null

Add-Type -AssemblyName System.Drawing
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$hdc = $graphics.GetHdc()
$printed = [PackagedHomeCapture]::PrintWindow($handle, $hdc, 2)
$graphics.ReleaseHdc($hdc)
$bitmap.Save($screenshot, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()

Get-Process KaraokeBuddy -ErrorAction SilentlyContinue | Stop-Process -Force

if (-not $printed) {
    throw "KaraokeBuddy home window opened, but screenshot capture failed."
}

[ordered]@{
    exe = $exe
    result = "opened_home_window"
    window_title = $visible.MainWindowTitle
    screenshot = $screenshot
    width = $width
    height = $height
} | ConvertTo-Json
