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

    /// <summary>
    /// Folder that holds cun_config.json / cache / log / icon. Uses the exe
    /// directory, falling back to its parent if the config lives one level up
    /// (i.e. the app was dropped into a sub-folder of the install). Matches the
    /// Python <c>data_dir()</c> behaviour.
    /// </summary>
    public static string DataDir()
    {
        var exeDir = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        if (!File.Exists(Path.Combine(exeDir, "cun_config.json")))
        {
            var parent = Path.GetDirectoryName(exeDir);
            if (parent != null && File.Exists(Path.Combine(parent, "cun_config.json")))
                return parent;
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
