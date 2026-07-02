using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace CunSorter.Services;

/// <summary>
/// Tiny localhost HTTP/SSE server that publishes the memory-read judgment data
/// to the DGHub plugin (same shape as Chuni2Api's /events stream, plus
/// settlement events carrying cun's 寸 verdict). The trigger logic and all
/// waveform/strength settings live in the DGHub plugin's own config page — cun
/// only serves data. Raw TcpListener, so no http.sys URL-ACL is needed.
/// </summary>
public sealed class LinkServerService
{
    private const int SnapshotIntervalMs = 100;         // SSE push cadence
    private const int StaleAfterMs = 2000;              // no tick that long ⇒ WAITING

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private readonly Action<string> _onStatus;

    private TcpListener? _listener;
    private CancellationTokenSource? _cts;
    private readonly object _lock = new();
    private JudgeCounts _counts;
    private long _lastTickTicks;                        // Environment.TickCount64 of last update
    private int _clients;
    private readonly List<System.Collections.Concurrent.ConcurrentQueue<string>> _eventQueues = new();

    public LinkServerService(Action<string> onStatus) => _onStatus = onStatus;

    public bool IsRunning => _listener != null;

    private void Status(string s)
    {
        try { _onStatus(s); } catch { /* ignore */ }
    }

    public void Start(int port)
    {
        if (IsRunning) return;
        try
        {
            _cts = new CancellationTokenSource();
            _listener = new TcpListener(IPAddress.Loopback, port);
            _listener.Start();
            var token = _cts.Token;
            _ = Task.Run(() => AcceptLoop(_listener, token));
            Status($"监听 127.0.0.1:{port}，等待插件连接");
        }
        catch (Exception e)
        {
            _listener = null;
            Status($"启动失败（端口 {port} 被占用？）：{e.Message}");
        }
    }

    public void Stop()
    {
        _cts?.Cancel();
        try { _listener?.Stop(); } catch { /* ignore */ }
        _listener = null;
        lock (_lock) _eventQueues.Clear();
    }

    /// <summary>Feed the latest counters (memory-reader thread, ~20 Hz).</summary>
    public void UpdateCounts(JudgeCounts c)
    {
        lock (_lock)
        {
            _counts = c;
            _lastTickTicks = Environment.TickCount64;
        }
    }

    /// <summary>Broadcast a settlement event to every connected client.</summary>
    public void PublishSettle(object payload)
    {
        var json = JsonSerializer.Serialize(payload, JsonOpts);
        lock (_lock)
            foreach (var q in _eventQueues)
                q.Enqueue(json);
    }

    private string SnapshotJson()
    {
        lock (_lock)
        {
            var stale = Environment.TickCount64 - _lastTickTicks > StaleAfterMs;
            var status = stale ? "WAITING" : _counts.Total == 0 ? "IN MENU" : "PLAYING";
            return JsonSerializer.Serialize(new
            {
                critical = _counts.Critical,
                justice = _counts.Justice,
                attack = _counts.Attack,
                miss = _counts.Miss,
                status,
            }, JsonOpts);
        }
    }

    // ----------------------------- serving ------------------------------------
    private async Task AcceptLoop(TcpListener listener, CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            TcpClient client;
            try { client = await listener.AcceptTcpClientAsync(token); }
            catch { return; }                            // listener stopped
            _ = Task.Run(() => ServeClient(client, token));
        }
    }

    private async Task ServeClient(TcpClient client, CancellationToken token)
    {
        using var _ = client;
        client.NoDelay = true;
        var stream = client.GetStream();

        string path;
        try { path = await ReadRequestPath(stream, token); }
        catch { return; }

        try
        {
            if (path.StartsWith("/events"))
            {
                await ServeSse(stream, token);
            }
            else if (path.StartsWith("/data"))
            {
                await WriteSimple(stream, "application/json", SnapshotJson(), token);
            }
            else
            {
                await WriteSimple(stream, "text/plain; charset=utf-8",
                    "今天你寸了吗 · DGHub 联动服务\n/events = SSE 判定流\n/data = 当前快照", token);
            }
        }
        catch { /* client gone */ }
    }

    private static async Task<string> ReadRequestPath(NetworkStream stream, CancellationToken token)
    {
        var buf = new byte[4096];
        var sb = new StringBuilder();
        while (!sb.ToString().Contains("\r\n\r\n"))
        {
            int n = await stream.ReadAsync(buf, token);
            if (n <= 0) throw new IOException("closed");
            sb.Append(Encoding.ASCII.GetString(buf, 0, n));
            if (sb.Length > 16384) break;                // header flood guard
        }
        var line = sb.ToString().Split("\r\n")[0].Split(' ');
        return line.Length >= 2 ? line[1] : "/";
    }

    private static async Task WriteSimple(NetworkStream stream, string contentType, string body, CancellationToken token)
    {
        var bytes = Encoding.UTF8.GetBytes(body);
        var hdr = $"HTTP/1.1 200 OK\r\nContent-Type: {contentType}\r\n" +
                  $"Access-Control-Allow-Origin: *\r\nContent-Length: {bytes.Length}\r\nConnection: close\r\n\r\n";
        await stream.WriteAsync(Encoding.ASCII.GetBytes(hdr), token);
        await stream.WriteAsync(bytes, token);
    }

    private async Task ServeSse(NetworkStream stream, CancellationToken token)
    {
        const string hdr = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n" +
                           "Cache-Control: no-cache\r\nAccess-Control-Allow-Origin: *\r\n" +
                           "Connection: keep-alive\r\n\r\n";
        await stream.WriteAsync(Encoding.ASCII.GetBytes(hdr), token);

        var queue = new System.Collections.Concurrent.ConcurrentQueue<string>();
        int n;
        lock (_lock) { _eventQueues.Add(queue); n = ++_clients; }
        Status($"插件已连接 ×{n}");
        try
        {
            while (!token.IsCancellationRequested)
            {
                while (queue.TryDequeue(out var evt))
                    await stream.WriteAsync(Encoding.UTF8.GetBytes($"data: {evt}\n\n"), token);
                await stream.WriteAsync(Encoding.UTF8.GetBytes($"data: {SnapshotJson()}\n\n"), token);
                await Task.Delay(SnapshotIntervalMs, token);
            }
        }
        finally
        {
            lock (_lock) { _eventQueues.Remove(queue); n = --_clients; }
            Status(n > 0 ? $"插件已连接 ×{n}" : "插件已断开，等待连接");
        }
    }
}
