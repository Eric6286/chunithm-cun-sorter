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

    /// <summary>Rule kinds that count as a 寸 hit (shared with the DGHub link's
    /// settlement judgment).</summary>
    public static readonly HashSet<string> CunKinds = new() { "score", "am", "ajcun" };
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
        long? size = null;
        try { size = new FileInfo(path).Length; } catch { /* size stays null */ }
        // Reuse the cache only when the on-disk file matches the cached size. The
        // cache is keyed by bare filename, so a same-named-but-different file (now
        // possible since scans recurse subfolders) would otherwise be classified
        // with the wrong record. A null cached size = legacy record → accept it.
        if (cache.TryGetValue(fn, out var rec) && (rec.Size is null || rec.Size == size))
            return rec;
        var r = ocr.Detect(path, cfg);
        rec = new OcrCacheRecord { Score = r.Score, Attack = r.Attack, Miss = r.Miss, Size = size };
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
                // "aj"/"fc" are legacy rule kinds (no longer creatable in the UI —
                // AJ/FC are tracked intrinsically via IsAj/IsFc). Kept for any
                // hand-authored config; the conditions mirror those predicates.
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

    /// <summary>Remove only files this tool created (named '*__*.png') from the
    /// output folders, recursively — so nested 寸/SSS寸 / 寸/AM寸 / FC copies (and
    /// any left over from an older version) are all cleared on a rebuild.</summary>
    public static int ClearToolFiles(CunConfig cfg)
    {
        int removed = 0;
        // Top-level segment of each rule folder (e.g. "寸/AJ寸" → "寸") plus the
        // intrinsic 寸 / AJ / FC roots; each is then recursed so subfolders count.
        var folders = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var c in cfg.Categories)
            if (!string.IsNullOrEmpty(c.Folder))
                folders.Add(c.Folder.Replace("\\", "/").Split('/')[0]);
        folders.Add(cfg.CunFolder);
        folders.Add(cfg.AjFolder);
        folders.Add("FC");
        foreach (var folder in folders)
        {
            if (string.IsNullOrEmpty(folder)) continue;
            var d = Path.Combine(cfg.OutputRoot, folder);
            if (!Directory.Exists(d)) continue;
            IEnumerable<string> files;
            try { files = Directory.EnumerateFiles(d, "*.png", SearchOption.AllDirectories); }
            catch { continue; }
            foreach (var f in files)
            {
                if (!Path.GetFileName(f).Contains("__")) continue;
                try { File.Delete(f); removed++; } catch { /* ignore */ }
            }
        }
        return removed;
    }

    // ----------------------------- organize ----------------------------------
    /// <summary>True if at least one organize dimension is switched on.</summary>
    public static bool OrganizeEnabled(CunConfig cfg) => cfg.Organize.Steps.Any(s => s.Enabled);

    /// <summary>AJ (All Justice): ATTACK=0 and MISS=0. Single definition shared by
    /// the organize folder, the scan counter and the daily stats.</summary>
    public static bool IsAj(OcrCacheRecord r) => r.Attack == 0 && r.Miss == 0;

    /// <summary>FC (Full Combo): MISS=0 with at least one ATTACK.</summary>
    public static bool IsFc(OcrCacheRecord r) => r.Miss == 0 && r.Attack is int a && a > 0;

    /// <summary>Nested sub-path (e.g. "2026-05/SSS+/AJ") from the enabled organize
    /// steps, in their configured order. A dimension that can't be resolved (no
    /// date in the filename, no score) is skipped rather than inventing an
    /// "unknown" folder; an empty result ⇒ the caller leaves the file in place.</summary>
    private static string OrganizeRelPath(string filename, OcrCacheRecord rec, CunConfig cfg)
    {
        var parts = new List<string>();
        foreach (var step in cfg.Organize.Steps)
        {
            if (!step.Enabled) continue;
            var seg = step.Kind switch
            {
                "date" => DateSegment(filename, step.DateSpan),
                "rank" => ConfigService.RankOf(rec.Score, cfg),
                "achievement" => AchievementSegment(rec),
                _ => null,
            };
            if (!string.IsNullOrEmpty(seg)) parts.Add(seg);
        }
        return string.Join("/", parts);
    }

    private static string? DateSegment(string filename, string span)
    {
        var m = DateRe.Match(filename);
        if (!m.Success) return null;               // no date in name → skip this dimension
        var d = m.Groups[1].Value;                 // yyyy-MM-dd
        return span switch { "year" => d[..4], "day" => d, _ => d[..7] };
    }

    private static string AchievementSegment(OcrCacheRecord rec) =>
        IsAj(rec) ? "AJ" : IsFc(rec) ? "FC" : "普通";

    /// <summary>The tool's own output folders (full paths), split in two groups.
    /// RuleRoots (寸 + the top segment of every rule folder) only ever receive our
    /// copies, so the scanner skips them wholesale by LOCATION — robust against
    /// user screenshots whose names happen to contain "__". AJ / FC however
    /// double as the ACHIEVEMENT-organize destinations: originals moved there by
    /// organize must still be scanned, so under those roots only files carrying
    /// the "__" copy marker (legacy AJ/FC rule copies) are skipped.</summary>
    private static (List<string> RuleRoots, List<string> AchievementRoots) ToolRoots(CunConfig cfg)
    {
        var ruleNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { cfg.CunFolder };
        foreach (var c in cfg.Categories)
            if (!string.IsNullOrEmpty(c.Folder))
                ruleNames.Add(c.Folder.Replace("\\", "/").Split('/')[0]);
        var achievementNames = new[] { cfg.AjFolder, "FC" }
            .Where(n => !string.IsNullOrEmpty(n) && !ruleNames.Contains(n));

        List<string> Resolve(IEnumerable<string> names)
        {
            var roots = new List<string>();
            foreach (var n in names)
            {
                if (string.IsNullOrEmpty(n)) continue;
                try { roots.Add(Path.GetFullPath(Path.Combine(cfg.OutputRoot, n))); } catch { /* skip */ }
            }
            return roots;
        }
        return (Resolve(ruleNames), Resolve(achievementNames));
    }

    private static bool IsUnder(string fullPath, IEnumerable<string> roots)
    {
        foreach (var r in roots)
            if (fullPath.Equals(r, StringComparison.OrdinalIgnoreCase) ||
                fullPath.StartsWith(r + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                return true;
        return false;
    }

    /// <summary>Move a recognised result screenshot into its organize folder
    /// (creating it). Skips files that aren't result screens (no score read), so
    /// unrelated images in the folder are never relocated. No-op if already in
    /// place; an identical file already at the destination is left as-is rather
    /// than spawning a "(N)" duplicate. Originals are moved, never deleted; the
    /// source directory is recorded so a folder it empties can be pruned.</summary>
    private static void MoveToOrganized(string path, OcrCacheRecord rec, CunConfig cfg,
        ICollection<string>? emptied = null)
    {
        if (rec.Score is null) return;             // not a result screen → leave it alone
        var rel = OrganizeRelPath(Path.GetFileName(path), rec, cfg);
        if (string.IsNullOrEmpty(rel)) return;
        var destDir = Path.Combine(new[] { cfg.OutputRoot }.Concat(rel.Split('/')).ToArray());
        var dest = Path.Combine(destDir, Path.GetFileName(path));
        if (PathsEqual(dest, path)) return;
        var srcDir = TryGetDir(path);
        try
        {
            // An identical file already archived under this name: don't move (would
            // create a "(N)" duplicate). Leave the source as-is (never deleted).
            if (File.Exists(dest) && SameSize(dest, path))
            {
                if (srcDir != null) emptied?.Add(srcDir);
                return;
            }
            Directory.CreateDirectory(destDir);
            File.Move(path, UniqueDest(dest));
            if (srcDir != null) emptied?.Add(srcDir);
        }
        catch (Exception e) { Log($"ERROR organize {Path.GetFileName(path)} -> {rel}: {e.Message}"); }
    }

    /// <summary>All original screenshots to process, found recursively under the
    /// screenshots dir and output root, EXCLUDING the tool's own output folders
    /// (寸 / AJ / FC / rule folders). Used for every scan; the organize switch only
    /// decides whether originals are then moved, so turning organize off still
    /// scans (and counts) files already archived in subfolders.</summary>
    private static List<string> ListOriginals(CunConfig cfg)
    {
        var (ruleRoots, achievementRoots) = ToolRoots(cfg);
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
                string full;
                try { full = Path.GetFullPath(f); } catch { continue; }
                if (IsUnder(full, ruleRoots)) continue;     // our own copy, not an original
                // AJ / FC hold both organized ORIGINALS (scan them) and legacy
                // rule copies (skip via the "__" marker OutName always adds).
                if (IsUnder(full, achievementRoots) && Path.GetFileName(full).Contains("__")) continue;
                if (seen.Add(full)) result.Add(f);
            }
        }
        return result;
    }

    private static string? TryGetDir(string path)
    {
        try { return Path.GetDirectoryName(Path.GetFullPath(path)); } catch { return null; }
    }

    private static bool SameSize(string a, string b)
    {
        try { return new FileInfo(a).Length == new FileInfo(b).Length; } catch { return false; }
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

    /// <summary>Prune only the directories this organize pass emptied (and any
    /// parents that became empty as a result), walking up to — but never deleting —
    /// the screenshots / output roots. Unlike a blanket sweep this never removes
    /// unrelated empty folders the user keeps under the output tree.</summary>
    private static void PruneEmptyDirsScoped(IEnumerable<string> dirs, CunConfig cfg)
    {
        var stop = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var r in new[] { cfg.ScreenshotsDir, cfg.OutputRoot })
            try { stop.Add(Path.GetFullPath(r)); } catch { /* skip */ }

        foreach (var d in dirs)
        {
            var dir = d;
            while (!string.IsNullOrEmpty(dir) && !stop.Contains(dir))
            {
                try
                {
                    if (Directory.Exists(dir) && !Directory.EnumerateFileSystemEntries(dir).Any())
                    {
                        var parent = Path.GetDirectoryName(dir);
                        Directory.Delete(dir);
                        dir = parent;
                    }
                    else break;
                }
                catch { break; }
            }
        }
    }

    // ----------------------------- scan / stats ------------------------------
    /// <summary>OCR + classify one screenshot: copy 寸 matches into 寸/ folders,
    /// then (when organize is on) MOVE the original into the date/rank/achievement
    /// tree. Shared by the full scan and the live watcher. <paramref name="emptied"/>
    /// collects source dirs left behind by a move, for scoped pruning.</summary>
    public static (OcrCacheRecord Rec, List<Category> Matches) ProcessFile(
        string path, CunConfig cfg, Dictionary<string, OcrCacheRecord> cache, OcrService ocr, bool organize,
        ICollection<string>? emptied = null)
    {
        var rec = GetOcr(path, cfg, cache, ocr);
        var matches = Classify(rec.Score, rec.Attack, rec.Miss, cfg);
        if (matches.Count > 0) CopyMatches(path, rec, matches, cfg);       // 寸 copies first
        if (organize) MoveToOrganized(path, rec, cfg, emptied);            // then move the original
        return (rec, matches);
    }

    public static ScanResult ScanAll(CunConfig cfg, OcrService ocr,
        Action<int, int, int, int>? progress = null, bool rebuild = false, bool reocr = false)
    {
        var cache = reocr ? new Dictionary<string, OcrCacheRecord>() : LoadCache();
        var organize = OrganizeEnabled(cfg);
        if (rebuild) ClearToolFiles(cfg);

        // Always enumerate recursively (excluding our own output folders) so files
        // already archived in subfolders are still scanned/counted even when
        // organize is off; organize only decides whether originals are then moved.
        var files = ListOriginals(cfg);
        files.Sort(StringComparer.Ordinal);

        var emptied = organize ? new HashSet<string>(StringComparer.OrdinalIgnoreCase) : null;
        int nCun = 0, nAj = 0;
        for (int i = 0; i < files.Count; i++)
        {
            var (rec, matches) = ProcessFile(files[i], cfg, cache, ocr, organize, emptied);
            if (matches.Any(c => CunKinds.Contains(c.Kind))) nCun++;
            if (IsAj(rec)) nAj++;                           // AJ is intrinsic now, not a rule
            int done = i + 1;
            if (progress != null && done % 5 == 0) progress(done, files.Count, nCun, nAj);
            if (done % 25 == 0) SaveCache(cache);
        }
        SaveCache(cache);
        if (emptied != null) PruneEmptyDirsScoped(emptied, cfg);
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
            if (IsAj(rec)) d[1]++;                          // AJ
            else if (IsFc(rec)) d[2]++;                     // FC
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
