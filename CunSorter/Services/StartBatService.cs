using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace CunSorter.Services;

/// <summary>
/// Hooks the game's start.bat so launching the game also launches this app in
/// watch mode. The injected line is
/// <c>start "chunithm-cun-sorter" "&lt;exe&gt;" --watch</c> — the quoted start
/// window title doubles as the removal marker. The file is edited at the BYTE
/// level (lines split on \n): existing line CONTENT keeps its exact bytes, so
/// we never re-encode someone's GBK/UTF-8 batch text. Our own line (the exe
/// path may contain Chinese) is encoded GBK by default, matching cmd's default
/// codepage on Chinese Windows, or UTF-8 when the bat has a BOM / `chcp 65001`.
/// Output is always joined with CRLF: cmd's batch parser is only reliable with
/// CRLF — in an LF-only bat it eats the first character of the line following
/// <c>@echo off</c>, turning our injected `start` into `tart` (observed live).
/// A one-time <c>*.cun-backup</c> copy is kept next to the original.
/// </summary>
public static class StartBatService
{
    private const string Marker = "chunithm-cun-sorter";

    public static bool IsHooked(string batPath)
    {
        try
        {
            return File.Exists(batPath) &&
                   SplitLines(File.ReadAllBytes(batPath)).Any(l => AsciiView(l).Contains(Marker));
        }
        catch { return false; }
    }

    /// <summary>Insert (or refresh) the auto-launch line after the leading
    /// <c>@echo off</c>, pointing at the currently running exe.</summary>
    public static void Hook(string batPath)
    {
        var exe = Environment.ProcessPath
                  ?? throw new InvalidOperationException("无法确定本程序的 exe 路径");
        var original = File.ReadAllBytes(batPath);

        var backup = batPath + ".cun-backup";
        if (!File.Exists(backup)) File.WriteAllBytes(backup, original);

        var lines = SplitLines(original).Where(l => !AsciiView(l).Contains(Marker)).ToList();

        bool utf8 = HasUtf8Bom(original) ||
                    lines.Any(l => AsciiView(l).ToLowerInvariant().Contains("chcp 65001"));
        var enc = utf8 ? new UTF8Encoding(false) : Encoding.GetEncoding(936);
        var cmd = enc.GetBytes($"start \"{Marker}\" \"{exe}\" --watch");

        int insertAt = 0;
        for (int i = 0; i < lines.Count; i++)
        {
            if (AsciiView(lines[i]).TrimStart().StartsWith("@echo", StringComparison.OrdinalIgnoreCase))
            {
                insertAt = i + 1;
                break;
            }
        }
        lines.Insert(insertAt, cmd);
        File.WriteAllBytes(batPath, JoinLines(lines));
    }

    /// <summary>Remove the auto-launch line (no-op if absent).</summary>
    public static void Unhook(string batPath)
    {
        if (!File.Exists(batPath)) return;
        var bytes = File.ReadAllBytes(batPath);
        var lines = SplitLines(bytes);
        var kept = lines.Where(l => !AsciiView(l).Contains(Marker)).ToList();
        if (kept.Count != lines.Count)
            File.WriteAllBytes(batPath, JoinLines(kept));
    }

    // ----------------------------- byte-level lines ---------------------------
    private static List<byte[]> SplitLines(byte[] bytes)
    {
        var lines = new List<byte[]>();
        int start = 0;
        for (int i = 0; i < bytes.Length; i++)
        {
            if (bytes[i] != (byte)'\n') continue;
            int end = i > start && bytes[i - 1] == (byte)'\r' ? i - 1 : i;
            lines.Add(bytes[start..end]);
            start = i + 1;
        }
        if (start < bytes.Length) lines.Add(bytes[start..]);
        return lines;
    }

    private static byte[] JoinLines(List<byte[]> lines)
    {
        using var ms = new MemoryStream();
        for (int i = 0; i < lines.Count; i++)
        {
            ms.Write(lines[i]);
            if (i < lines.Count - 1) ms.Write("\r\n"u8);
        }
        ms.Write("\r\n"u8);                              // keep a trailing newline
        return ms.ToArray();
    }

    /// <summary>Latin-1 view of a line: ASCII bytes map 1:1 in both GBK and
    /// UTF-8, so marker/keyword substring checks are encoding-safe.</summary>
    private static string AsciiView(byte[] line) => Encoding.Latin1.GetString(line);

    private static bool HasUtf8Bom(byte[] b) =>
        b.Length >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF;
}
