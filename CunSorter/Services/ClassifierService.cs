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

    // ----------------------------- scan / stats ------------------------------
    public static ScanResult ScanAll(CunConfig cfg, OcrService ocr,
        Action<int, int, int, int>? progress = null, bool rebuild = false, bool reocr = false)
    {
        var cache = reocr ? new Dictionary<string, OcrCacheRecord>() : LoadCache();
        var sdir = cfg.ScreenshotsDir;
        var files = ListPngs(sdir);
        files.Sort(StringComparer.Ordinal);
        if (rebuild) ClearToolFiles(cfg);
        int nCun = 0, nAj = 0;
        for (int i = 0; i < files.Count; i++)
        {
            var full = Path.Combine(sdir, files[i]);
            var rec = GetOcr(full, cfg, cache, ocr);
            var matches = Classify(rec.Score, rec.Attack, rec.Miss, cfg);
            if (matches.Count > 0)
            {
                CopyMatches(full, rec, matches, cfg);
                var kinds = matches.Select(c => c.Kind).ToHashSet();
                if (kinds.Overlaps(CunKinds)) nCun++;
                if (kinds.Contains("aj")) nAj++;
            }
            int done = i + 1;
            if (progress != null && done % 5 == 0) progress(done, files.Count, nCun, nAj);
            if (done % 25 == 0) SaveCache(cache);
        }
        SaveCache(cache);
        progress?.Invoke(files.Count, files.Count, nCun, nAj);
        return new ScanResult { Total = files.Count, Cun = nCun, Aj = nAj };
    }

    /// <summary>Sorted (date, cunCount, ajCount) derived from cache + config.</summary>
    public static List<(string Date, int Cun, int Aj)> DailyCounts(CunConfig cfg,
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
            if (!days.TryGetValue(date, out var d)) days[date] = d = new int[2];
            if (kinds.Overlaps(CunKinds)) d[0]++;
            if (kinds.Contains("aj")) d[1]++;
        }
        return days.OrderBy(kv => kv.Key, StringComparer.Ordinal)
                   .Select(kv => (kv.Key, kv.Value[0], kv.Value[1])).ToList();
    }
}

public class ScanResult
{
    public int Total { get; set; }
    public int Cun { get; set; }
    public int Aj { get; set; }
    public string? Error { get; set; }
}
