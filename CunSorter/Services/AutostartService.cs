using System;
using System.Diagnostics;
using Microsoft.Win32;

namespace CunSorter.Services;

/// <summary>
/// Run-at-login toggle via HKCU\...\Run. Mirrors the autostart helpers in
/// <c>cun_gui.py</c>, but points at the compiled .exe instead of pythonw.exe.
/// </summary>
public static class AutostartService
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";

    private static string ExePath()
    {
        try
        {
            var p = Process.GetCurrentProcess().MainModule?.FileName;
            if (!string.IsNullOrEmpty(p)) return p!;
        }
        catch { /* ignore */ }
        return Environment.ProcessPath ?? AppContext.BaseDirectory;
    }

    public static bool IsEnabled()
    {
        try
        {
            using var k = Registry.CurrentUser.OpenSubKey(RunKey);
            return k?.GetValue(App.AppName) != null;
        }
        catch { return false; }
    }

    public static void Set(bool enabled)
    {
        try
        {
            using var k = Registry.CurrentUser.OpenSubKey(RunKey, writable: true)
                          ?? Registry.CurrentUser.CreateSubKey(RunKey);
            if (k == null) return;
            if (enabled) k.SetValue(App.AppName, $"\"{ExePath()}\"");
            else { try { k.DeleteValue(App.AppName); } catch { /* missing */ } }
        }
        catch { /* best effort */ }
    }
}
