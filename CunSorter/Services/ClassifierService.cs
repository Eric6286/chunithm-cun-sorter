using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using CunSorter.Models;

namespace CunSorter.Services;

/// <summary>
/// Classification, copying, scanning, caching and daily stats. Faithful port of
/// the non-watcher half of <c>cun_core.py</c>. OCR results are cached in
/// cun_ocr_cache.json so re-classifying with new bounds is instant (no re-OCR).
/// </summary>
public static class ClassifierService
{
    public static readonly string CachePath = Path.Combine(ConfigService.Here, "cun_ocr_cache.json");
    public static readonly string LogPath = Path.Combine(ConfigService.Here, "cun.log");

    private static readonly HashSet<string> CunKinds = new() { "score", "am", "ajcun" };
    private static readonly Regex DateRe = new(@"^(\d{4}-\d{2}-\d{2})", RegexOptions.Compiled);

    public static string Log(string msg)
    {
        var line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + msg;
        try { File.AppendAllText(LogPath, line + "\n"); } catch { /* ignore */ }
        return line;
    }

    public static List<string> ListPngs(string dir)
    {
        try
        {
            return Directory.EnumerateFiles(dir)
                .Where(f => f.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                .Select(Path.GetFileName).Where(f => f != null).Select(f => f!).ToList();
        }
        catch { return new List<string>(); }
    }

    // ----------------------------- cache -------------------------------------
    public static Dictionary<string, OcrCacheRecord> LoadCache()
    {
        if (File.Exists(CachePath))
        {
            try
            {
                return JsonSerializer.Deserialize<Dictionary<string, OcrCacheRecord>>(File.ReadAllText(CachePath))
                       ?? new();
            }
            catch { /* ignore */ }
        }
        return new();
    }

    public static void SaveCache(Dictionary<string, OcrCacheRecord> cache)
    {
        var tmp = CachePath + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(cache));
        if (File.Exists(CachePath)) File.Delete(CachePath);
        File.Move(tmp, CachePath);
    }

    /// <summary>Return cached OCR for a file, running detection on first sight.</summary>
    public static OcrCacheRecord GetOcr(string path, CunConfig cfg,
        Dictionary<string, OcrCacheRecord> cache, OcrService ocr)
    {
        var fn = Path.GetFileName(path);
        if (cache.TryGetValue(fn, out var rec)) return rec;
        var r = ocr.Detect(path, cfg);
        rec = new OcrCacheRecord { Score = r.Score, Attack = r.Attack, Miss = r.Miss };
        cache[fn] = rec;
        return rec;
    }

    // ----------------------------- classify ----------------------------------
    public static List<Category> Classify(int? s, int? a, int? m, CunConfig cfg)
    {
        var outp = new List<Category>();
        foreach (var cat in cfg.Categories)
        {
            if (!cat.Enabled) continue;
            switch (cat.Kind)
            {
                case "aj":   // All Justice
                    if (a == 0 && m == 0) outp.Add(cat);
                    break;
                case "fc":   // Full Combo: A!=0, M=0
                    if (a is not null && m is not null && a != 0 && m == 0) outp.Add(cat);
                    break;
                case "ajcun":   // 差点 AJ: A=0, 0<M<=x
                    if (a == 0 && m is not null && m > 0 && m <= (cat.MHi ?? 4)) outp.Add(cat);
                    break;
                case "score":
                    if (s is not null && (cat.Lo ?? 0) <= s && s <= (cat.Hi ?? 0)) outp.Add(cat);
                    break;
                case "am":   // A<=a_hi, M<=m_hi, A+M>0, rank>=floor
                    if (s is not null && a is not null && m is not null)
                    {
                        int floor = cat.MinRank is not null
                            ? (cfg.RankThresholds.TryGetValue(cat.MinRank, out var t) ? t : 1007500)
                            : (cat.ScoreMin ?? 1007500);
                        if (s >= floor && a <= (cat.AHi ?? 4) && m <= (cat.MHi ?? 4) && (a + m) > 0)
                            outp.Add(cat);
                    }
                    break;
            }
        }
        return outp;
    }

    // ----------------------------- copy --------------------------------------
    private static string Sanitize(string s) =>
        s.Replace("+", "p").Replace("/", "_").Replace("\\", "_");

    private static string NoneStr(int? x) => x?.ToString() ?? "None";

    private static string OutName(string b, string ext, string? rank, OcrCacheRecord rec,
        List<Category> cats, bool rename)
    {
        var tag = string.Join("+", cats.Select(c => Sanitize(c.Key)));
        if (rename)
            return $"{b}__{tag}_{Sanitize(rank ?? "NA")}_A{NoneStr(rec.Attack)}M{NoneStr(rec.Miss)}_{NoneStr(rec.Score)}{ext}";
        return $"{b}__{tag}{ext}";
    }

    /// <summary>Copy the screenshot into each target folder for its matched categories.</summary>
    public static List<string> CopyMatches(string path, OcrCacheRecord rec, List<Category> matches, CunConfig cfg)
    {
        var byFolder = new Dictionary<string, List<Category>>();
        foreach (var c in matches)
        {
            var folder = string.IsNullOrEmpty(c.Folder) ? cfg.CunFolder : c.Folder;
            if (!byFolder.TryGetValue(folder, out var list)) byFolder[folder] = list = new();
            list.Add(c);
        }
        var b = Path.GetFileNameWithoutExtension(path);
        var ext = Path.GetExtension(path);
        var rank = ConfigService.RankOf(rec.Score, cfg);
        var rename = cfg.RenameWithStats;
        var copied = new List<string>();
        foreach (var (folder, cats) in byFolder)
        {
            var parts = folder.Replace("\\", "/").Split('/');   // support nested e.g. 寸/AJ寸
            var d = Path.Combine(new[] { cfg.OutputRoot }.Concat(parts).ToArray());
            try
            {
                Directory.CreateDirectory(d);
                var dst = Path.Combine(d, OutName(b, ext, rank, rec, cats, rename));
                if (!File.Exists(dst)) File.Copy(path, dst);
                copied.Add(dst);
            }
            catch (Exception e)
            {
                Log($"ERROR copying {Path.GetFileName(path)} -> {folder}: {e.Message}");
            }
        }
        return copied;
    }

    /// <summary>Remove only files this tool created (named '*__*') from the output folders.</summary>
    public static int ClearToolFiles(CunConfig cfg)
    {
        int removed = 0;
        var folders = new HashSet<string>(cfg.Categories.Where(c => !string.IsNullOrEmpty(c.Folder)).Select(c => c.Folder));
        folders.Add(cfg.CunFolder);
        folders.Add(cfg.AjFolder);
        foreach (var folder in folders)
        {
            var d = Path.Combine(cfg.OutputRoot, folder);
            if (!Directory.Exists(d)) continue;
            foreach (var f in Directory.EnumerateFiles(d))
            {
                var name = Path.GetFileName(f);
                if (name.Contains("__") && name.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                {
                    try { File.Delete(f); removed++; } catch { /* ignore */ }
                }
            }
        }
        return removed;
    }

    // ----------------------------- organize ----------------------------------
    /// <summary>True if at least one organize dimension is switched on.</summary>
    public static bool OrganizeEnabled(CunConfig cfg) => cfg.Organize.Steps.Any(s => s.Enabled);

    /// <summary>Nested sub-path (e.g. "2026-05/SSS+/AJ") from the enabled organize
    /// steps, in their configured order; empty when nothing is enabled.</summary>
    private static string OrganizeRelPath(string filename, OcrCacheRecord rec, CunConfig cfg)
    {
        var parts = new List<string>();
        foreach (var step in cfg.Organize.Steps)
        {
            if (!step.Enabled) continue;
            var seg = step.Kind switch
            {
                "date" => DateSegment(filename, step.DateSpan),
                "rank" => ConfigService.RankOf(rec.Score, cfg) ?? "未知评级",
                "achievement" => AchievementSegment(rec),
                _ => null,
            };
            if (!string.IsNullOrEmpty(seg)) parts.Add(seg);
        }
        return string.Join("/", parts);
    }

    private static string DateSegment(string filename, string span)
    {
        var m = DateRe.Match(filename);
        if (!m.Success) return "未知日期";
        var d = m.Groups[1].Value;                 // yyyy-MM-dd
        return span switch { "year" => d[..4], "day" => d, _ => d[..7] };
    }

    private static string AchievementSegment(OcrCacheRecord rec)
    {
        if (rec.Attack is int a && rec.Miss is int m)
        {
            if (a == 0 && m == 0) return "AJ";     // All Justice
            if (m == 0) return "FC";               // Full Combo
        }
        return "普通";
    }

    /// <summary>Move the original screenshot into its organize folder (creating it).
    /// No-op if it is already there. Originals are moved, never deleted.</summary>
    private static void MoveToOrganized(string path, OcrCacheRecord rec, CunConfig cfg)
    {
        var rel = OrganizeRelPath(Path.GetFileName(path), rec, cfg);
        if (string.IsNullOrEmpty(rel)) return;
        var destDir = Path.Combine(new[] { cfg.OutputRoot }.Concat(rel.Split('/')).ToArray());
        var dest = Path.Combine(destDir, Path.GetFileName(path));
        if (PathsEqual(dest, path)) return;
        try
        {
            Directory.CreateDirectory(destDir);
            File.Move(path, UniqueDest(dest));
        }
        catch (Exception e) { Log($"ERROR organize {Path.GetFileName(path)} -> {rel}: {e.Message}"); }
    }

    /// <summary>Originals (files without our "__" tag) under the screenshots dir and
    /// output root, recursively — so already-organized files are re-evaluated when
    /// the organize order changes.</summary>
    private static List<string> ListOriginals(CunConfig cfg)
    {
        var roots = new List<string> { cfg.ScreenshotsDir };
        if (!PathsEqual(cfg.OutputRoot, cfg.ScreenshotsDir)) roots.Add(cfg.OutputRoot);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var result = new List<string>();
        foreach (var root in roots)
        {
            if (!Directory.Exists(root)) continue;
            IEnumerable<string> all;
            try { all = Directory.EnumerateFiles(root, "*.png", SearchOption.AllDirectories); }
            catch { continue; }
            foreach (var f in all)
            {
                if (Path.GetFileName(f).Contains("__")) continue;   // our own 寸 copy
                if (seen.Add(Path.GetFullPath(f))) result.Add(f);
            }
        }
        return result;
    }

    private static bool PathsEqual(string a, string b)
    {
        try { return string.Equals(Path.GetFullPath(a), Path.GetFullPath(b), StringComparison.OrdinalIgnoreCase); }
        catch { return false; }
    }

    private static string UniqueDest(string dest)
    {
        if (!File.Exists(dest)) return dest;
        var dir = Path.GetDirectoryName(dest)!;
        var b = Path.GetFileNameWithoutExtension(dest);
        var ext = Path.GetExtension(dest);
        for (int i = 1; ; i++)
        {
            var cand = Path.Combine(dir, $"{b} ({i}){ext}");
            if (!File.Exists(cand)) return cand;
        }
    }

    private static void PruneEmptyDirs(string root)
    {
        try
        {
            foreach (var dir in Directory.EnumerateDirectories(root, "*", SearchOption.AllDirectories)
                         .OrderByDescending(d => d.Length))
                try { if (!Directory.EnumerateFileSystemEntries(dir).Any()) Directory.Delete(dir); }
                catch { /* in use / not empty */ }
        }
        catch { /* root gone */ }
    }

    // ----------------------------- scan / stats ------------------------------
    /// <summary>OCR + classify one screenshot: copy 寸 matches into 寸/ folders,
    /// then (when organize is on) MOVE the original into the date/rank/achievement
    /// tree. Shared by the full scan and the live watcher.</summary>
    public static (OcrCacheRecord Rec, List<Category> Matches) ProcessFile(
        string path, CunConfig cfg, Dictionary<string, OcrCacheRecord> cache, OcrService ocr, bool organize)
    {
        var rec = GetOcr(path, cfg, cache, ocr);
        var matches = Classify(rec.Score, rec.Attack, rec.Miss, cfg);
        if (matches.Count > 0) CopyMatches(path, rec, matches, cfg);   // 寸 copies first
        if (organize) MoveToOrganized(path, rec, cfg);                 // then move the original
        return (rec, matches);
    }

    public static ScanResult ScanAll(CunConfig cfg, OcrService ocr,
        Action<int, int, int, int>? progress = null, bool rebuild = false, bool reocr = false)
    {
        var cache = reocr ? new Dictionary<string, OcrCacheRecord>() : LoadCache();
        var organize = OrganizeEnabled(cfg);
        if (rebuild) ClearToolFiles(cfg);

        var files = organize
            ? ListOriginals(cfg)
            : ListPngs(cfg.ScreenshotsDir).Select(f => Path.Combine(cfg.ScreenshotsDir, f)).ToList();
        files.Sort(StringComparer.Ordinal);

        int nCun = 0, nAj = 0;
        for (int i = 0; i < files.Count; i++)
        {
            var (rec, matches) = ProcessFile(files[i], cfg, cache, ocr, organize);
            if (matches.Select(c => c.Kind).ToHashSet().Overlaps(CunKinds)) nCun++;
            if (rec.Attack == 0 && rec.Miss == 0) nAj++;   // AJ is intrinsic now, not a rule
            int done = i + 1;
            if (progress != null && done % 5 == 0) progress(done, files.Count, nCun, nAj);
            if (done % 25 == 0) SaveCache(cache);
        }
        SaveCache(cache);
        if (organize) PruneEmptyDirs(cfg.OutputRoot);
        progress?.Invoke(files.Count, files.Count, nCun, nAj);
        return new ScanResult { Total = files.Count, Cun = nCun, Aj = nAj };
    }

    /// <summary>Sorted (date, cunCount, ajCount, fcCount) derived from cache + config.
    /// AJ and FC are intrinsic: AJ = A0/M0, FC = M0 with attacks.</summary>
    public static List<(string Date, int Cun, int Aj, int Fc)> DailyCounts(CunConfig cfg,
        Dictionary<string, OcrCacheRecord>? cache = null)
    {
        cache ??= LoadCache();
        var days = new Dictionary<string, int[]>();
        foreach (var (fn, rec) in cache)
        {
            var mobj = DateRe.Match(fn);
            if (!mobj.Success) continue;
            var date = mobj.Groups[1].Value;
            var kinds = Classify(rec.Score, rec.Attack, rec.Miss, cfg).Select(c => c.Kind).ToHashSet();
            if (!days.TryGetValue(date, out var d)) days[date] = d = new int[3];
            if (kinds.Overlaps(CunKinds)) d[0]++;
            if (rec.Attack == 0 && rec.Miss == 0) d[1]++;                       // AJ
            else if (rec.Miss == 0 && rec.Attack is int a && a > 0) d[2]++;     // FC
        }
        return days.OrderBy(kv => kv.Key, StringComparer.Ordinal)
                   .Select(kv => (kv.Key, kv.Value[0], kv.Value[1], kv.Value[2])).ToList();
    }
}

public class ScanResult
{
    public int Total { get; set; }
    public int Cun { get; set; }
    public int Aj { get; set; }
    public string? Error { get; set; }
}
