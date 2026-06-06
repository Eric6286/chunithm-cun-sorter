using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Encodings.Web;
using System.Text.Json;
using CunSorter.Models;
using CunSorter.Native;

namespace CunSorter.Services;

/// <summary>
/// Loads/saves cun_config.json and resolves portable paths. Mirrors the config
/// half of <c>cun_detect.py</c> (load_config / save_config / rank_of).
/// </summary>
public static class ConfigService
{
    public static readonly string Here = NativeUtil.DataDir();
    public static readonly string ConfigPath = Path.Combine(Here, "cun_config.json");

    private static readonly JsonSerializerOptions WriteOpts = new()
    {
        WriteIndented = true,
        // ensure_ascii=False equivalent: keep 寸 / Chinese folder names literal.
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    /// <summary>Built-in defaults, matching the DEFAULTS dict in cun_detect.py.</summary>
    private static CunConfig Defaults() => new()
    {
        Categories = new List<Category>
        {
            new() { Key = "AJ", Label = "AJ", Kind = "aj", Enabled = true, Folder = "AJ" },
            new() { Key = "FC", Label = "FC", Kind = "fc", Enabled = true, Folder = "FC" },
            new() { Key = "AJ寸", Label = "AJ 寸", Kind = "ajcun", Enabled = true, Folder = "寸/AJ寸", MHi = 4 },
            new() { Key = "SSS+寸", Label = "SSS+ 寸", Kind = "score", Enabled = true, Folder = "寸/SSS+寸", Lo = 1008600, Hi = 1008999 },
            new() { Key = "SSS寸", Label = "SSS 寸", Kind = "score", Enabled = true, Folder = "寸/SSS寸", Lo = 1007000, Hi = 1007499 },
            new() { Key = "SS+寸", Label = "SS+ 寸", Kind = "score", Enabled = true, Folder = "寸/SS+寸", Lo = 1004500, Hi = 1004999 },
            new() { Key = "SS寸", Label = "SS 寸", Kind = "score", Enabled = true, Folder = "寸/SS寸", Lo = 999500, Hi = 999999 },
            new() { Key = "AM寸", Label = "ATTACK+MISS", Kind = "am", Enabled = true, Folder = "寸/AM寸", AHi = 4, MHi = 4, MinRank = "SSS" },
        }
    };

    public static CunConfig Load(string? path = null)
    {
        path ??= ConfigPath;
        var cfg = Defaults();
        if (File.Exists(path))
        {
            try
            {
                var user = JsonSerializer.Deserialize<CunConfig>(File.ReadAllText(path));
                if (user != null)
                {
                    // Mirror the Python key-by-key overlay: keep defaults for any
                    // section the user file omits, and merge box entries rather
                    // than replacing the whole dict.
                    if (user.Categories.Count == 0) user.Categories = cfg.Categories;
                    if (user.RankThresholds.Count == 0) user.RankThresholds = cfg.RankThresholds;
                    foreach (var (k, v) in cfg.Boxes)
                        user.Boxes.TryAdd(k, v);
                    cfg = user;
                }
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"config load failed ({e.Message}); using defaults");
            }
        }

        // Portable path resolution: drop the app folder into <CHUNITHM>\bin and it
        // finds <CHUNITHM>\bin\screenshots automatically.
        var baseDir = Path.GetDirectoryName(Here) ?? Here;
        if (string.IsNullOrEmpty(cfg.ScreenshotsDir))
            cfg.ScreenshotsDir = Path.GetFullPath(Path.Combine(baseDir, "screenshots"));
        if (string.IsNullOrEmpty(cfg.OutputRoot))
            cfg.OutputRoot = cfg.ScreenshotsDir;

        // Tesseract: keep the configured path; otherwise fall back to PATH.
        if (!File.Exists(cfg.TesseractCmd))
        {
            var found = WhichTesseract();
            if (found != null) cfg.TesseractCmd = found;
        }
        return cfg;
    }

    public static void Save(CunConfig cfg, string? path = null)
    {
        path ??= ConfigPath;
        var tmp = path + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(cfg, WriteOpts));
        if (File.Exists(path)) File.Delete(path);
        File.Move(tmp, path);
    }

    public static string? RankOf(int? score, CunConfig cfg)
    {
        if (score is null) return null;
        foreach (var (name, thr) in cfg.RankThresholds.OrderByDescending(kv => kv.Value))
            if (score >= thr) return name;
        return "D";
    }

    /// <summary>Ranks sorted high → low, for the config-page combo box.</summary>
    public static List<string> Ranks(CunConfig cfg) =>
        cfg.RankThresholds.OrderByDescending(kv => kv.Value).Select(kv => kv.Key).ToList();

    private static string? WhichTesseract()
    {
        var pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (var dir in pathEnv.Split(Path.PathSeparator))
        {
            if (string.IsNullOrWhiteSpace(dir)) continue;
            var candidate = Path.Combine(dir, "tesseract.exe");
            if (File.Exists(candidate)) return candidate;
        }
        return null;
    }
}
