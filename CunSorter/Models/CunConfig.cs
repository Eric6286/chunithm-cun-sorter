using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace CunSorter.Models;

/// <summary>
/// Strongly-typed mirror of <c>cun_config.json</c>. Property names map to the
/// original snake_case keys so the file round-trips unchanged between the Python
/// tool and this WinUI 3 port.
/// </summary>
public class CunConfig
{
    [JsonPropertyName("screenshots_dir")] public string ScreenshotsDir { get; set; } = "";
    [JsonPropertyName("output_root")] public string OutputRoot { get; set; } = "";
    [JsonPropertyName("cun_folder")] public string CunFolder { get; set; } = "寸";
    [JsonPropertyName("aj_folder")] public string AjFolder { get; set; } = "AJ";
    [JsonPropertyName("tesseract_cmd")] public string TesseractCmd { get; set; } = @"C:\Program Files\Tesseract-OCR\tesseract.exe";
    [JsonPropertyName("process_mode")] public string ProcessMode { get; set; } = "realtime";
    [JsonPropertyName("game_process")] public string GameProcess { get; set; } = "chusanApp.exe";
    [JsonPropertyName("game_poll_sec")] public double GamePollSec { get; set; } = 4;
    [JsonPropertyName("game_exit_grace_sec")] public double GameExitGraceSec { get; set; } = 20;
    [JsonPropertyName("rename_with_stats")] public bool RenameWithStats { get; set; } = true;
    [JsonPropertyName("expected_size")] public int[] ExpectedSize { get; set; } = { 1920, 1080 };
    [JsonPropertyName("dark_threshold")] public int DarkThreshold { get; set; } = 95;
    [JsonPropertyName("bright_threshold")] public int BrightThreshold { get; set; } = 110;

    [JsonPropertyName("boxes")]
    public Dictionary<string, int[]> Boxes { get; set; } = new()
    {
        ["top_line1"] = new[] { 558, 6, 1345, 40 },
        ["top_line2"] = new[] { 760, 42, 1345, 82 },
        ["bd_atk"] = new[] { 824, 758, 921, 792 },
        ["bd_miss"] = new[] { 824, 806, 921, 840 },
    };

    [JsonPropertyName("rank_thresholds")]
    public Dictionary<string, int> RankThresholds { get; set; } = new()
    {
        ["SSS+"] = 1009000, ["SSS"] = 1007500, ["SS+"] = 1005000, ["SS"] = 1000000,
        ["S+"] = 990000, ["S"] = 975000, ["AAA"] = 950000, ["AA"] = 925000, ["A"] = 900000,
        ["BBB"] = 800000, ["BB"] = 700000, ["B"] = 600000, ["C"] = 500000, ["D"] = 0,
    };

    [JsonPropertyName("categories")]
    public List<Category> Categories { get; set; } = new();

    [JsonPropertyName("organize")]
    public OrganizeConfig Organize { get; set; } = new();
}

/// <summary>
/// "Organize all screenshots" settings. Each enabled step contributes one nested
/// folder level; <see cref="Steps"/> order is the nesting order (first = outermost).
/// When any step is enabled, originals are MOVED into the resulting folder tree.
/// </summary>
public class OrganizeConfig
{
    [JsonPropertyName("steps")]
    public List<OrganizeStep> Steps { get; set; } = new()
    {
        new() { Kind = "date", DateSpan = "month" },
        new() { Kind = "rank" },
        new() { Kind = "achievement" },
    };
}

/// <summary>One organize dimension: by date, by rank, or by achievement (AJ/FC).</summary>
public class OrganizeStep
{
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";        // date | rank | achievement
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("date_span")] public string DateSpan { get; set; } = "month";   // year | month | day
}

/// <summary>One classification rule (a row in the GUI config page).</summary>
public class Category
{
    [JsonPropertyName("key")] public string Key { get; set; } = "";
    [JsonPropertyName("label")] public string Label { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "";
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("folder")] public string Folder { get; set; } = "";

    // True for rules the user added in-app; built-in defaults omit it. Drives the
    // default-vs-custom grouping on the config page.
    [JsonPropertyName("custom")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] public bool Custom { get; set; }

    // Optional, kind-specific bounds (null when not applicable → omitted on save).
    [JsonPropertyName("lo")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public int? Lo { get; set; }
    [JsonPropertyName("hi")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public int? Hi { get; set; }
    [JsonPropertyName("m_hi")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public int? MHi { get; set; }
    [JsonPropertyName("a_hi")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public int? AHi { get; set; }
    [JsonPropertyName("min_rank")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public string? MinRank { get; set; }
    [JsonPropertyName("score_min")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public int? ScoreMin { get; set; }
}
