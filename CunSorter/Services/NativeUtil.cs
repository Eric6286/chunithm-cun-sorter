using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace CunSorter.Native;

/// <summary>
/// Win32 / process helpers. Mirrors the ctypes bits of <c>cun_core.py</c> and
/// the <c>data_dir()</c> logic of <c>cun_detect.py</c>.
/// </summary>
public static class NativeUtil
{
    [DllImport("shell32.dll", PreserveSig = false)]
    private static extern void SetCurrentProcessExplicitAppUserModelID(
        [MarshalAs(UnmanagedType.LPWStr)] string appId);

    public static void SetAppUserModelId(string id) => SetCurrentProcessExplicitAppUserModelID(id);

    [DllImport("dwmapi.dll", PreserveSig = true)]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

    private const int DWMWA_USE_IMMERSIVE_DARK_MODE = 20;   // Win10 20H1+ / Win11

    /// <summary>
    /// Force the window's title-bar caption (strip + min/max/close glyphs) into
    /// dark mode via DWM, independent of the system light/dark setting. The XAML
    /// RequestedTheme only themes client content, not the system-drawn caption, so
    /// on a light-mode OS the title bar would otherwise stay white.
    /// </summary>
    public static void EnableDarkTitleBar(IntPtr hwnd)
    {
        try
        {
            int on = 1;
            DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ref on, sizeof(int));
        }
        catch { /* attribute unsupported on pre-20H1 builds */ }
    }

    /// <summary>
    /// Folder that holds cun_config.json / cache / log / icon. Walks up from the
    /// exe directory and returns the first ancestor that contains
    /// cun_config.json. A packaged deployment keeps the config one level up (exe
    /// in <c>bin\cun\app\</c>, config in <c>bin\cun\</c>); under <c>dotnet run</c>
    /// the exe is buried several levels deep in <c>bin\Release\…\win-x64</c>, so a
    /// single-parent check isn't enough. If no ancestor has the config (first
    /// run), fall back to the exe directory. Generalises the Python
    /// <c>data_dir()</c> behaviour.
    /// </summary>
    public static string DataDir()
    {
        var exeDir = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        var dir = exeDir;
        while (!string.IsNullOrEmpty(dir))
        {
            if (File.Exists(Path.Combine(dir, "cun_config.json")))
                return dir;
            dir = Path.GetDirectoryName(dir);
        }
        return exeDir;
    }

    /// <summary>Drop our own process to IDLE priority so OCR never steals frames.</summary>
    public static bool SetIdlePriority()
    {
        try
        {
            Process.GetCurrentProcess().PriorityClass = ProcessPriorityClass.Idle;
            return true;
        }
        catch { return false; }
    }

    /// <summary>True if a process with the given image name (e.g. "chusanApp.exe") is running.</summary>
    public static bool IsProcessRunning(string name)
    {
        if (string.IsNullOrWhiteSpace(name)) return false;
        var bare = name;
        if (bare.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            bare = bare[..^4];
        try
        {
            return Process.GetProcessesByName(bare).Length > 0;
        }
        catch { return false; }
    }
}
