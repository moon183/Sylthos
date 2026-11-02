param([Parameter(Mandatory=$true)][string]$Executable,
      [Parameter(Mandatory=$true)][string]$Receipt)
$ErrorActionPreference = 'Stop'
$exePath = (Resolve-Path -LiteralPath $Executable).Path
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class AssistantSmokeWindows {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder t, int n);
    public static string[] Titles(int pid) {
        var titles = new List<string>();
        EnumWindows((h,l) => { uint p; GetWindowThreadProcessId(h,out p);
            if(p==(uint)pid) { var t=new StringBuilder(512);GetWindowText(h,t,512);
                if(t.Length>0) titles.Add(t.ToString()); }
            return true; },IntPtr.Zero);
        return titles.ToArray();
    }
}
'@
$smokeProcess = Start-Process -FilePath $exePath -WorkingDirectory (Split-Path -Parent $exePath) -WindowStyle Hidden -PassThru
$titles = @()
$mainReady = $false
try {
    for ($attempt=0; $attempt -lt 80; $attempt++) {
        Start-Sleep -Milliseconds 250
        $smokeProcess.Refresh()
        if ($smokeProcess.HasExited) { break }
        $titles = @([AssistantSmokeWindows]::Titles($smokeProcess.Id))
        if ($titles -contains 'Sylthos') { $mainReady=$true; break }
    }
    $result = [ordered]@{mainWindowConstructed=$mainReady; executable=$exePath;
        windowTitles=$titles; devicesStarted=$false; networkRequested=$false;
        sha256=(Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash}
    $json = $result | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($Receipt),$json,[System.Text.UTF8Encoding]::new($false))
    $json
} finally {
    $smokeProcess.Refresh()
    if (-not $smokeProcess.HasExited) {
        if (-not $smokeProcess.CloseMainWindow()) { $smokeProcess.Kill() }
        $smokeProcess.WaitForExit(5000) | Out-Null
        if (-not $smokeProcess.HasExited) { $smokeProcess.Kill() }
    }
}
if (-not $mainReady) { exit 1 }
