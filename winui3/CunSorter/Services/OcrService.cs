using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using CunSorter.Models;
using Tesseract;

namespace CunSorter.Services;

/// <summary>
/// CHUNITHM result-screen OCR. Faithful port of <c>cun_detect.py</c>'s detect():
/// isolates the dark text outline of the top status bar so the white SCORE /
/// ATTACK / MISS glyphs become crisp, then reads them with Tesseract. The big
/// rainbow score/rank glyphs are intentionally NOT OCR'd.
/// </summary>
public sealed class OcrService : IDisposable
{
    private readonly object _lock = new();
    private TesseractEngine? _engine;
    private string? _engineDataPath;

    /// <summary>Resolve the tessdata folder from the configured tesseract.exe, else a local one.</summary>
    private static string? ResolveTessData(CunConfig cfg)
    {
        var cmdDir = Path.GetDirectoryName(cfg.TesseractCmd);
        if (!string.IsNullOrEmpty(cmdDir))
        {
            var td = Path.Combine(cmdDir, "tessdata");
            if (Directory.Exists(td) && File.Exists(Path.Combine(td, "eng.traineddata")))
                return td;
        }
        var local = Path.Combine(ConfigService.Here, "tessdata");
        if (Directory.Exists(local) && File.Exists(Path.Combine(local, "eng.traineddata")))
            return local;
        return null;
    }

    private TesseractEngine? GetEngine(CunConfig cfg)
    {
        var dataPath = ResolveTessData(cfg);
        if (dataPath == null) return null;
        lock (_lock)
        {
            if (_engine != null && _engineDataPath == dataPath) return _engine;
            _engine?.Dispose();
            _engine = new TesseractEngine(dataPath, "eng", EngineMode.Default);
            _engineDataPath = dataPath;
            return _engine;
        }
    }

    // --------------------------- image preprocessing -------------------------
    private static Rectangle ScaledBox(int[] box, int w, int h, int[] exp)
    {
        if (w == exp[0] && h == exp[1])
            return Rectangle.FromLTRB(box[0], box[1], box[2], box[3]);
        double sx = (double)w / exp[0], sy = (double)h / exp[1];
        return Rectangle.FromLTRB(
            (int)(box[0] * sx), (int)(box[1] * sy),
            (int)(box[2] * sx), (int)(box[3] * sy));
    }

    /// <summary>
    /// Crop, upscale ×4, grayscale, then binarise. <paramref name="darkBelow"/>
    /// true → topbar mode (p &lt; th → black); false → breakdown mode (p &gt; th → black).
    /// </summary>
    private static Bitmap PrepRegion(Bitmap src, Rectangle box, int threshold, bool darkBelow, int scale = 4)
    {
        var rect = Rectangle.Intersect(box, new Rectangle(0, 0, src.Width, src.Height));
        if (rect.Width <= 0 || rect.Height <= 0)
            rect = new Rectangle(0, 0, Math.Min(1, src.Width), Math.Min(1, src.Height));

        using var crop = src.Clone(rect, PixelFormat.Format24bppRgb);
        var scaled = new Bitmap(crop.Width * scale, crop.Height * scale, PixelFormat.Format24bppRgb);
        using (var g = Graphics.FromImage(scaled))
        {
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.DrawImage(crop, new Rectangle(0, 0, scaled.Width, scaled.Height));
        }

        // Grayscale (ITU-R 601-2, matching PIL "L") + threshold, in one LockBits pass.
        var data = scaled.LockBits(new Rectangle(0, 0, scaled.Width, scaled.Height),
            ImageLockMode.ReadWrite, PixelFormat.Format24bppRgb);
        try
        {
            int stride = data.Stride;
            int bytes = stride * scaled.Height;
            var buf = new byte[bytes];
            System.Runtime.InteropServices.Marshal.Copy(data.Scan0, buf, 0, bytes);
            for (int y = 0; y < scaled.Height; y++)
            {
                int row = y * stride;
                for (int x = 0; x < scaled.Width; x++)
                {
                    int i = row + x * 3;
                    int b = buf[i], gr = buf[i + 1], r = buf[i + 2];
                    int lum = (r * 299 + gr * 587 + b * 114) / 1000;
                    bool black = darkBelow ? lum < threshold : lum > threshold;
                    byte v = black ? (byte)0 : (byte)255;
                    buf[i] = buf[i + 1] = buf[i + 2] = v;
                }
            }
            System.Runtime.InteropServices.Marshal.Copy(buf, 0, data.Scan0, bytes);
        }
        finally { scaled.UnlockBits(data); }
        return scaled;
    }

    private string Ocr(TesseractEngine engine, Bitmap bmp, PageSegMode psm, string? whitelist = null)
    {
        lock (_lock)
        {
            engine.SetVariable("tessedit_char_whitelist", whitelist ?? "");
            using var ms = new MemoryStream();
            bmp.Save(ms, ImageFormat.Png);
            using var pix = Pix.LoadFromMemory(ms.ToArray());
            using var page = engine.Process(pix, psm);
            return (page.GetText() ?? "").Trim();
        }
    }

    // --------------------------- text parsing --------------------------------
    private static int? ParseScore(string text)
    {
        // Collapse stray spaces between digit groups (e.g. "1,007 ,603").
        text = Regex.Replace(text, @"(?<=[\d,])\s+(?=[\d,])", "");
        int? best = null;
        foreach (Match tok in Regex.Matches(text, @"[\d,]+"))
        {
            var d = Regex.Replace(tok.Value, @"\D", "");
            if (d.Length is >= 6 and <= 7 && int.TryParse(d, out int v) && v is >= 100000 and <= 1010000)
                if (best is null || v > best) best = v;
        }
        return best;
    }

    private static int? FindInt(string pattern, string text, int? lo = null, int? hi = null)
    {
        foreach (Match m in Regex.Matches(text, pattern, RegexOptions.IgnoreCase))
        {
            if (m.Groups.Count < 2 || !int.TryParse(m.Groups[1].Value, out int v)) continue;
            if ((lo is null || v >= lo) && (hi is null || v <= hi)) return v;
        }
        return null;
    }

    // --------------------------- detect --------------------------------------
    public OcrResult Detect(string path, CunConfig cfg)
    {
        var outp = new OcrResult { File = Path.GetFileName(path), Path = path };
        TesseractEngine? engine;
        try { engine = GetEngine(cfg); }
        catch (Exception e) { outp.Note = "ocr_engine_error: " + e.Message; return outp; }
        if (engine == null) { outp.Note = "ocr_engine_unavailable"; return outp; }

        Bitmap img;
        try { img = new Bitmap(path); }
        catch (Exception e) { outp.Note = "open_failed: " + e.Message; return outp; }

        using (img)
        {
            int w = img.Width, h = img.Height;
            var exp = cfg.ExpectedSize;
            var B = cfg.Boxes;
            int darkTh = cfg.DarkThreshold, brightTh = cfg.BrightThreshold;

            string t1, t2;
            using (var l1Img = PrepRegion(img, ScaledBox(B["top_line1"], w, h, exp), darkTh, true))
                t1 = Ocr(engine, l1Img, PageSegMode.SingleLine);

            using var l2Img = PrepRegion(img, ScaledBox(B["top_line2"], w, h, exp), darkTh, true);
            t2 = Ocr(engine, l2Img, PageSegMode.SingleLine);

            outp.RawLine1 = t1;
            outp.RawLine2 = t2;

            // ATTACK / MISS: label present ⟺ ≥1; label absent ⟺ 0 (overlay hides 0).
            var ut = t1.ToUpperInvariant();
            var (attack, asrc) = TopField(ut, "ATTACK", t1, @"ATTACK\D{0,4}(\d{1,4})");
            var (miss, msrc) = TopField(ut, "MISS", t1, @"MISS\D{0,4}(\d{1,4})");

            int? score = ParseScore(t2);
            if (score is null)
            {
                var t2b = Ocr(engine, l2Img, PageSegMode.SingleBlock);
                var s2 = ParseScore(t2b);
                if (s2 is not null) { score = s2; outp.RawLine2 = t2 + " || psm6:" + t2b; }
            }

            var notes = new System.Collections.Generic.List<string>();
            if (asrc == "unread")
            {
                using var bdImg = PrepRegion(img, ScaledBox(B["bd_atk"], w, h, exp), brightTh, false);
                var bd = FindInt(@"(\d{1,4})", Ocr(engine, bdImg, PageSegMode.SingleWord, "0123456789"), 0, 9999);
                if (bd is not null) { attack = bd; notes.Add("attack_from_breakdown"); }
            }
            if (msrc == "unread")
            {
                using var bdImg = PrepRegion(img, ScaledBox(B["bd_miss"], w, h, exp), brightTh, false);
                var bd = FindInt(@"(\d{1,4})", Ocr(engine, bdImg, PageSegMode.SingleWord, "0123456789"), 0, 9999);
                if (bd is not null) { miss = bd; notes.Add("miss_from_breakdown"); }
            }

            outp.Score = score;
            outp.Attack = attack;
            outp.Miss = miss;
            outp.Rank = ConfigService.RankOf(score, cfg);
            outp.Note = string.Join(";", notes);
        }
        return outp;
    }

    private static (int?, string) TopField(string upper, string label, string raw, string regex)
    {
        if (!upper.Contains(label)) return (0, "zero");
        var m = Regex.Match(raw, regex, RegexOptions.IgnoreCase);
        if (m.Success && int.TryParse(m.Groups[1].Value, out int v)) return (v, "top");
        return (null, "unread");
    }

    public void Dispose() => _engine?.Dispose();
}
