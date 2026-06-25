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

    /// <summary>
    /// Built-in defaults. Judgment rules now start empty — the user builds them in
    /// the 自定义判定 list (the former preset rules are offered as options in the
    /// add dialog). Rank thresholds / OCR boxes / organize steps come from the
    /// <see cref="CunConfig"/> property initializers.
    /// </summary>
    private static CunConfig Defaults() => new();

    /// <summary>Built-in 评级判定 score presets (name + inclusive bounds). Single
    /// source of truth shared by the add-rule dialog and the v1.1→v1.2 migration —
    /// the former lived in the now-removed default Categories.</summary>
    public static readonly (string Name, int Lo, int Hi)[] ScorePresets =
    {
        ("SSS+寸", 1008600, 1008999),
        ("SSS寸", 1007000, 1007499),
        ("SS+寸", 1004500, 1004999),
        ("SS寸", 999500, 999999),
    };

    /// <summary>Keys of the v1.1 built-in preset rules. On upgrade these are
    /// dropped (re-creatable from the add dialog), but any OTHER rule is kept and
    /// treated as user-defined — so a user's hand-added rules and renamed/retuned
    /// custom rules are NOT lost just because the old file predates the `custom`
    /// flag.</summary>
    private static readonly HashSet<string> LegacyBuiltinKeys = new()
    {
        "AJ", "FC", "AJ寸", "AM寸", "SSS+寸", "SSS寸", "SS+寸", "SS寸",
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
                    // Keep defaults for any section the user file omits, and merge
                    // box entries rather than replacing the whole dict.
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

        // v1.1→v1.2 migration: drop only the legacy built-in presets (re-creatable
        // from the add dialog). Keep every other rule — a user's hand-added or
        // retuned rule from a file that predates the `custom` flag would otherwise
        // be silently wiped. Survivors are marked custom so later loads leave them
        // alone and the config page groups them correctly.
        cfg.Categories = cfg.Categories
            .Where(c => c.Custom || !LegacyBuiltinKeys.Contains(c.Key))
            .ToList();
        foreach (var c in cfg.Categories) c.Custom = true;
        EnsureOrganizeSteps(cfg);

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

    private static CunConfig? _cached;
    private static DateTime _cachedStamp;
    private static readonly object _loadLock = new();

    /// <summary>
    /// Cached <see cref="Load"/> for hot paths (the watcher polls every couple of
    /// seconds): re-reads cun_config.json only when its last-write time changes,
    /// otherwise returns the previously parsed instance — avoiding a full file
    /// read + JSON deserialize + Tesseract PATH probe on every tick. Callers must
    /// treat the result as read-only (it is shared); use <see cref="Load"/> when a
    /// private mutable snapshot is needed (e.g. a background rescan).
    /// </summary>
    public static CunConfig LoadCached()
    {
        lock (_loadLock)
        {
            try
            {
                var stamp = File.Exists(ConfigPath)
                    ? File.GetLastWriteTimeUtc(ConfigPath)
                    : DateTime.MinValue;
                if (_cached != null && stamp == _cachedStamp) return _cached;
                _cached = Load();
                _cachedStamp = stamp;
                return _cached;
            }
            catch
            {
                return _cached ?? Load();
            }
        }
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

    /// <summary>The three organize dimensions in canonical order, used when a
    /// config omits one.</summary>
    private static readonly string[] OrganizeKinds = { "date", "rank", "achievement" };

    /// <summary>Keep the user's ordering but guarantee all three organize steps
    /// exist exactly once and drop any unknown kind.</summary>
    private static void EnsureOrganizeSteps(CunConfig cfg)
    {
        cfg.Organize ??= new OrganizeConfig();
        var steps = cfg.Organize.Steps
            .Where(s => OrganizeKinds.Contains(s.Kind))
            .GroupBy(s => s.Kind).Select(g => g.First()).ToList();
        foreach (var kind in OrganizeKinds)
            if (!steps.Any(s => s.Kind == kind))
                steps.Add(new OrganizeStep { Kind = kind });
        cfg.Organize.Steps = steps;
    }

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
