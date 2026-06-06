using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using CunSorter.Services;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Shapes;
using Windows.Foundation;
using Windows.UI;

namespace CunSorter.Pages;

/// <summary>
/// Daily 「寸」 statistics: four summary cards plus a hand-drawn line chart
/// (寸 + AJ series) on a Canvas. Mirrors <c>StatsInterface</c> in cun_gui.py.
/// </summary>
public sealed partial class StatsPage : Page
{
    private readonly MainWindow _main;
    private List<(string Date, int Cun, int Aj)> _data = new();

    public StatsPage(MainWindow main)
    {
        _main = main;
        InitializeComponent();
    }

    private void Refresh_Click(object sender, RoutedEventArgs e) => Refresh();
    private void Chart_SizeChanged(object sender, SizeChangedEventArgs e) => DrawChart();

    public void Refresh()
    {
        var cfg = ConfigService.Load();
        _data = ClassifierService.DailyCounts(cfg);

        var now = DateTime.Now;
        var today = now.ToString("yyyy-MM-dd");
        int tc = _data.FirstOrDefault(d => d.Date == today).Cun;
        int total = _data.Sum(d => d.Cun);
        var weekDays = Enumerable.Range(0, 7).Select(i => now.AddDays(-i).ToString("yyyy-MM-dd")).ToHashSet();
        int week = _data.Where(d => weekDays.Contains(d.Date)).Sum(d => d.Cun);
        var best = _data.Count > 0 ? _data.OrderByDescending(d => d.Cun).First() : default;

        ValToday.Text = tc.ToString();
        ValWeek.Text = week.ToString();
        ValTotal.Text = total.ToString();
        if (_data.Count > 0 && best.Cun > 0)
        {
            ValBest.Text = best.Cun.ToString();
            CapBest.Text = "最高一天 · " + best.Date[5..];
        }
        else { ValBest.Text = "0"; CapBest.Text = "最高一天"; }

        RangeLabel.Text = _data.Count > 0
            ? $"统计区间 {_data[0].Date} ~ {_data[^1].Date}    ·    更新于 {now:HH:mm:ss}"
            : "暂无数据    ·    更新于 " + now.ToString("HH:mm:ss");

        DrawChart();
    }

    private static Brush Res(string key, Color fallback)
    {
        if (Application.Current.Resources.TryGetValue(key, out var v) && v is Brush b) return b;
        return new SolidColorBrush(fallback);
    }

    private void DrawChart()
    {
        var canvas = ChartCanvas;
        canvas.Children.Clear();
        double w = canvas.ActualWidth, h = canvas.ActualHeight;
        if (w <= 1 || h <= 1) return;

        var fg = Res("TextFillColorPrimaryBrush", Colors.Gray);
        var sub = Res("TextFillColorSecondaryBrush", Colors.Gray);
        var gridBrush = new SolidColorBrush(Color.FromArgb(40, 128, 128, 128));
        var accent = Res("AccentFillColorDefaultBrush", Color.FromArgb(255, 0, 120, 215));
        var ajBrush = new SolidColorBrush(Color.FromArgb(255, 255, 180, 70));

        if (_data.Count == 0)
        {
            var empty = new TextBlock { Text = "暂无数据", Foreground = sub };
            Canvas.SetLeft(empty, w / 2 - 30);
            Canvas.SetTop(empty, h / 2 - 10);
            canvas.Children.Add(empty);
            return;
        }

        const double L = 44, R = 18, T = 16, B = 40;
        double plotW = Math.Max(1, w - L - R);
        double plotH = Math.Max(1, h - T - B);

        int ymax = Math.Max(1, _data.Max(d => Math.Max(d.Cun, d.Aj)));
        int yTop = ymax + 1;

        double Xpos(int i) => _data.Count == 1 ? L + plotW / 2 : L + plotW * i / (_data.Count - 1);
        double Ypos(double v) => T + plotH * (1 - v / yTop);

        // y gridlines + labels
        int step = yTop <= 10 ? 1 : (int)Math.Ceiling(yTop / 10.0);
        for (int v = 0; v <= yTop; v += step)
        {
            double y = Ypos(v);
            canvas.Children.Add(MakeLine(L, y, L + plotW, y, gridBrush, 1));
            var lbl = new TextBlock { Text = v.ToString(), Foreground = sub, FontSize = 11 };
            Canvas.SetLeft(lbl, 6);
            Canvas.SetTop(lbl, y - 8);
            canvas.Children.Add(lbl);
        }

        // x labels (up to 8, evenly spaced)
        int labelCount = Math.Min(8, Math.Max(2, _data.Count));
        var shown = new HashSet<int>();
        for (int k = 0; k < labelCount; k++)
            shown.Add(_data.Count == 1 ? 0 : (int)Math.Round((double)k * (_data.Count - 1) / (labelCount - 1)));
        foreach (var i in shown)
        {
            var date = DateTime.ParseExact(_data[i].Date, "yyyy-MM-dd", CultureInfo.InvariantCulture);
            var lbl = new TextBlock { Text = date.ToString("M/d"), Foreground = sub, FontSize = 11 };
            Canvas.SetLeft(lbl, Xpos(i) - 12);
            Canvas.SetTop(lbl, T + plotH + 8);
            canvas.Children.Add(lbl);
        }

        // AJ line (orange dashed)
        var ajPts = new PointCollection();
        for (int i = 0; i < _data.Count; i++) ajPts.Add(new Point(Xpos(i), Ypos(_data[i].Aj)));
        canvas.Children.Add(new Polyline
        {
            Points = ajPts, Stroke = ajBrush, StrokeThickness = 2,
            StrokeDashArray = new DoubleCollection { 4, 3 },
        });
        for (int i = 0; i < _data.Count; i++)
            canvas.Children.Add(MakeDot(Xpos(i), Ypos(_data[i].Aj), ajBrush, 3));

        // 寸 line (accent, thicker) with value labels
        var cunPts = new PointCollection();
        for (int i = 0; i < _data.Count; i++) cunPts.Add(new Point(Xpos(i), Ypos(_data[i].Cun)));
        canvas.Children.Add(new Polyline { Points = cunPts, Stroke = accent, StrokeThickness = 3 });
        for (int i = 0; i < _data.Count; i++)
        {
            double x = Xpos(i), y = Ypos(_data[i].Cun);
            canvas.Children.Add(MakeDot(x, y, accent, 4));
            var vl = new TextBlock { Text = _data[i].Cun.ToString(), Foreground = fg, FontSize = 11 };
            Canvas.SetLeft(vl, x - 5);
            Canvas.SetTop(vl, y - 20);
            canvas.Children.Add(vl);
        }

        // legend
        AddLegend(canvas, w - 120, 4, accent, "寸");
        AddLegend(canvas, w - 70, 4, ajBrush, "AJ");
    }

    private static Line MakeLine(double x1, double y1, double x2, double y2, Brush b, double th) => new()
    {
        X1 = x1, Y1 = y1, X2 = x2, Y2 = y2, Stroke = b, StrokeThickness = th,
    };

    private static Ellipse MakeDot(double x, double y, Brush b, double r)
    {
        var e = new Ellipse { Width = r * 2, Height = r * 2, Fill = b };
        Canvas.SetLeft(e, x - r);
        Canvas.SetTop(e, y - r);
        return e;
    }

    private void AddLegend(Canvas canvas, double x, double y, Brush b, string text)
    {
        var dot = new Ellipse { Width = 10, Height = 10, Fill = b };
        Canvas.SetLeft(dot, x);
        Canvas.SetTop(dot, y + 4);
        canvas.Children.Add(dot);
        var lbl = new TextBlock { Text = text, Foreground = Res("TextFillColorPrimaryBrush", Colors.Gray), FontSize = 12 };
        Canvas.SetLeft(lbl, x + 16);
        Canvas.SetTop(lbl, y);
        canvas.Children.Add(lbl);
    }
}
