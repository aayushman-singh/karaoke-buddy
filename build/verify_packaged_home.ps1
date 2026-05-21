$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$exe = Join-Path $root "build/dist/KaraokeBuddy.exe"
$screenshot = Join-Path $root "docs/packaged-home.png"

python (Join-Path $root "build/build.py")

if (!(Test-Path $exe)) {
    throw "Packaged exe was not created at $exe"
}

Get-Process KaraokeBuddy -ErrorAction SilentlyContinue | Stop-Process -Force

function Get-LaunchedProcessIds {
    param([int]$RootProcessId)

    $processIds = New-Object System.Collections.Generic.List[int]
    $pending = New-Object System.Collections.Generic.Queue[int]
    $pending.Enqueue($RootProcessId)

    while ($pending.Count -gt 0) {
        $processId = $pending.Dequeue()
        if ($processIds.Contains($processId)) {
            continue
        }

        $processIds.Add($processId)
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $processId" |
            ForEach-Object { $pending.Enqueue([int]$_.ProcessId) }
    }

    $processIds.ToArray()
}

$launcher = $null

try {
    $launcher = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -PassThru
    $visible = $null

    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 1
        $launchedProcessIds = Get-LaunchedProcessIds -RootProcessId $launcher.Id
        $visible = Get-Process -Id $launchedProcessIds -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -eq "KaraokeBuddy" -and $_.MainWindowHandle -ne 0 } |
            Select-Object -First 1
        if ($visible) {
            break
        }
        $launcher.Refresh()
        if ($launcher.HasExited -and $launchedProcessIds.Count -eq 1) {
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
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@

    try {
        Add-Type -TypeDefinition $captureApi -ErrorAction Stop
    }
    catch {
        throw "Failed to compile PackagedHomeCapture used by $PSCommandPath. Error: $($_.Exception.Message)"
    }

    [PackagedHomeCapture]::SetProcessDPIAware() | Out-Null

    $handle = $visible.MainWindowHandle
    [PackagedHomeCapture]::MoveWindow($handle, 120, 80, 1280, 840, $true) | Out-Null
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
}
finally {
    if ($launcher) {
        $launchedProcessIds = Get-LaunchedProcessIds -RootProcessId $launcher.Id
        [array]::Reverse($launchedProcessIds)
        foreach ($processId in $launchedProcessIds) {
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                Stop-Process -Id $processId -Force
            }
        }
    }
}
