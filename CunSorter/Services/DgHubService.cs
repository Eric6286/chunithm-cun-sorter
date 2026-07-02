using System;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using CunSorter.Models;

namespace CunSorter.Services;

/// <summary>
/// Minimal DGHub external-plugin client. Instead of being spawned by DGHub, we
/// self-connect the documented debug way: pull the session token from
/// <c>GET /api/plugins/_session_token</c>, open the plugin WebSocket, complete
/// the <c>hello</c> handshake, then expose fire-and-forget <c>trigger</c> sends.
/// Reconnects with backoff until stopped; honours a server <c>stop</c> by going
/// dormant until the link is toggled again.
/// </summary>
public sealed class DgHubService
{
    private const string PluginId = "cun_sorter";
    private const string PluginVersion = "1.3.0";
    private const int ReconnectDelayMs = 5000;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private readonly Func<CunConfig> _getCfg;
    private readonly Action<string> _onStatus;
    private readonly Action<string>? _onLog;

    private CancellationTokenSource? _cts;
    private Task? _task;
    private ClientWebSocket? _ws;
    private readonly SemaphoreSlim _sendLock = new(1, 1);
    private volatile bool _connected;

    public DgHubService(Func<CunConfig> getCfg, Action<string> onStatus, Action<string>? onLog = null)
    {
        _getCfg = getCfg;
        _onStatus = onStatus;
        _onLog = onLog;
    }

    public bool IsRunning => _task is { IsCompleted: false };
    public bool IsConnected => _connected;

    public void Start()
    {
        if (IsRunning) return;
        _cts = new CancellationTokenSource();
        var token = _cts.Token;
        _task = Task.Run(() => RunAsync(token), token);
    }

    public void Stop()
    {
        _cts?.Cancel();
        try { _ws?.Abort(); } catch { /* ignore */ }
    }

    private void Status(string s)
    {
        try { _onStatus(s); } catch { /* ignore */ }
    }

    private void Log(string s)
    {
        try { _onLog?.Invoke(s); } catch { /* ignore */ }
    }

    // ----------------------------- connection loop ----------------------------
    private async Task RunAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            var cfg = _getCfg().DgHub;
            if (cfg.Port <= 0)
            {
                Status("未配置 DGHub 端口");
                if (await Delay(30_000, token)) return;
                continue;
            }
            try
            {
                var stopped = await ConnectOnceAsync(cfg.Host, cfg.Port, token);
                _connected = false;
                if (stopped)
                {
                    // DGHub asked us to stop (user disabled the plugin there):
                    // stay dormant instead of nagging with reconnects.
                    Status("已被 DGHub 停止（在 cun 里重新开关联动可重连）");
                    return;
                }
                Status("连接断开，5 秒后重连…");
            }
            catch (OperationCanceledException) { return; }
            catch (Exception e)
            {
                _connected = false;
                Status($"连接失败：{Brief(e)}，5 秒后重试…");
            }
            if (await Delay(ReconnectDelayMs, token)) return;
        }
    }

    private static async Task<bool> Delay(int ms, CancellationToken token)
    {
        try { await Task.Delay(ms, token); return false; }
        catch (OperationCanceledException) { return true; }
    }

    private static string Brief(Exception e)
    {
        var msg = e.InnerException?.Message ?? e.Message;
        return msg.Length > 120 ? msg[..120] + "…" : msg;
    }

    /// <summary>One full connect → handshake → receive session. Returns true if
    /// the server requested a stop (do not reconnect).</summary>
    private async Task<bool> ConnectOnceAsync(string host, int port, CancellationToken token)
    {
        Status("获取 DGHub 会话 token…");
        string tokenStr;
        using (var http = new HttpClient { Timeout = TimeSpan.FromSeconds(5) })
        {
            var body = await http.GetStringAsync($"http://{host}:{port}/api/plugins/_session_token", token);
            tokenStr = ParseToken(body);
        }

        using var ws = new ClientWebSocket();
        _ws = ws;
        try
        {
            Status("连接 DGHub…");
            await ws.ConnectAsync(new Uri($"ws://{host}:{port}/ws/plugin?token={Uri.EscapeDataString(tokenStr)}"), token);

            await SendAsync(ws, new
            {
                op = "hello",
                token = tokenStr,
                manifest = new
                {
                    id = PluginId,
                    name = "今天你寸了吗",
                    version = PluginVersion,
                    sdk = "1",
                    author = "cun",
                    description = "CHUNITHM 判定内存联动：实时 MISS/ATTACK 与结算「寸」判定触发",
                },
            }, token);

            var ack = await ReceiveAsync(ws, token);
            if (ack == null) return false;
            using (ack)
            {
                var root = ack.RootElement;
                if (root.TryGetProperty("op", out var op) && op.GetString() == "hello_ack" &&
                    root.TryGetProperty("accepted", out var acc) && !acc.GetBoolean())
                {
                    var reason = root.TryGetProperty("reason", out var r) ? r.GetString() : null;
                    Status($"DGHub 拒绝接入：{reason ?? "未知原因"}");
                    return true;    // config/SDK problem — retrying won't help
                }
            }

            _connected = true;
            Status("已连接 DGHub ●");
            await SendAsync(ws, new
            {
                op = "status",
                fields = new { display_status = "等待游戏数据" },
            }, token);

            while (!token.IsCancellationRequested)
            {
                var doc = await ReceiveAsync(ws, token);
                if (doc == null) return false;          // closed by server
                using (doc)
                {
                    var root = doc.RootElement;
                    var op = root.TryGetProperty("op", out var o) ? o.GetString() : null;
                    switch (op)
                    {
                        case "ping":
                            double? t = root.TryGetProperty("t", out var tv) && tv.ValueKind == JsonValueKind.Number
                                ? tv.GetDouble() : null;
                            await SendAsync(ws, new { op = "pong", t }, token);
                            break;
                        case "stop":
                            return true;
                        // config / config_changed / device_info: our settings live
                        // in cun's own UI, so nothing to apply here.
                    }
                }
            }
            return false;
        }
        finally
        {
            _connected = false;
            _ws = null;
        }
    }

    private static string ParseToken(string body)
    {
        try
        {
            using var doc = JsonDocument.Parse(body);
            var root = doc.RootElement;
            if (root.ValueKind == JsonValueKind.String) return root.GetString() ?? "";
            if (root.ValueKind == JsonValueKind.Object)
                foreach (var name in new[] { "token", "session_token", "data" })
                    if (root.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String)
                        return v.GetString() ?? "";
        }
        catch (JsonException) { /* plain-text body */ }
        return body.Trim().Trim('"');
    }

    // ----------------------------- send helpers -------------------------------
    private async Task SendAsync(ClientWebSocket ws, object payload, CancellationToken token)
    {
        var json = JsonSerializer.Serialize(payload, JsonOpts);
        var bytes = Encoding.UTF8.GetBytes(json);
        await _sendLock.WaitAsync(token);
        try { await ws.SendAsync(bytes, WebSocketMessageType.Text, true, token); }
        finally { _sendLock.Release(); }
    }

    private static async Task<JsonDocument?> ReceiveAsync(ClientWebSocket ws, CancellationToken token)
    {
        var buf = new byte[16 * 1024];
        var sb = new System.IO.MemoryStream();
        while (true)
        {
            var res = await ws.ReceiveAsync(buf, token);
            if (res.MessageType == WebSocketMessageType.Close) return null;
            sb.Write(buf, 0, res.Count);
            if (res.EndOfMessage) break;
        }
        try { return JsonDocument.Parse(sb.ToArray()); }
        catch (JsonException) { return JsonDocument.Parse("{}"); }
    }

    /// <summary>Fire a strength+waveform trigger (rollback: auto-returns to
    /// baseline after <paramref name="durationS"/>). No-op while disconnected.</summary>
    public void Trigger(int deltaPct, double durationS, string label)
    {
        var ws = _ws;
        if (ws is not { State: WebSocketState.Open } || !_connected) return;
        var cfg = _getCfg().DgHub;
        var payload = new
        {
            op = "trigger",
            action = "both",
            delta_pct = Math.Clamp(deltaPct, -100, 100),
            strength_mode = "rollback",
            duration_s = Math.Clamp(durationS, 0.0, 300.0),
            preset = cfg.Preset,
            channel = cfg.Channel,
            label,
        };
        _ = FireAsync(ws, payload, label);
    }

    /// <summary>Update the DGHub-side status card. No-op while disconnected.</summary>
    public void SendDisplayStatus(string text)
    {
        var ws = _ws;
        if (ws is not { State: WebSocketState.Open } || !_connected) return;
        _ = FireAsync(ws, new { op = "status", fields = new { display_status = text } }, null);
    }

    private async Task FireAsync(ClientWebSocket ws, object payload, string? label)
    {
        try
        {
            await SendAsync(ws, payload, CancellationToken.None);
            if (label != null) Log($"⚡ {label}");
        }
        catch (Exception e) { Status($"发送失败：{Brief(e)}"); }
    }
}
