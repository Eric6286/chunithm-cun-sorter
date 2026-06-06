using System.Text.Json.Serialization;

namespace CunSorter.Models;

/// <summary>
/// Result of OCR'ing one screenshot. Mirrors the dict returned by Python
/// <c>cun_detect.detect()</c>. Only Score/Attack/Miss are persisted in the cache.
/// </summary>
public class OcrResult
{
    public string File { get; set; } = "";
    public string Path { get; set; } = "";
    public int? Score { get; set; }
    public int? Attack { get; set; }
    public int? Miss { get; set; }
    public string? Rank { get; set; }
    public string Note { get; set; } = "";
    public string RawLine1 { get; set; } = "";
    public string RawLine2 { get; set; } = "";
}

/// <summary>Cached OCR record (cun_ocr_cache.json maps filename → this).</summary>
public class OcrCacheRecord
{
    [JsonPropertyName("score")] public int? Score { get; set; }
    [JsonPropertyName("attack")] public int? Attack { get; set; }
    [JsonPropertyName("miss")] public int? Miss { get; set; }
}
