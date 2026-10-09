#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
#endregion

// ============================================================================
//  DZ_SW_WsBridge_S021 — СЕРВЕР ПУЛЬТА РЕАЛЬНОГО ВРЕМЕНИ, v1.0 (2026-09-28)
//
//  Минимальный WebSocket (RFC 6455) поверх TcpListener, без внешних библиотек:
//  Fleck и Watson — чужие DLL в папке NinjaTrader; HttpListener требует
//  резервирования адреса правами администратора.
//
//  БЕЗОПАСНОСТЬ — браузер умеет открыть ws://127.0.0.1 с ЛЮБОГО сайта:
//    • только 127.0.0.1;
//    • Origin: разрешены только file://, null и app://atlas — чужие сайты отвергаются;
//    • ключ: первое сообщение клиента {"cmd":"auth","token":"…"}; без ключа — ни данных,
//      ни команд. Ключ лежит в файле пользователя, создаётся один раз;
//    • команды — закрытый список: pause, resume, flatten; не больше одной в секунду;
//    • сообщение клиента — не больше 4 КБ; клиентов — не больше 4.
//
//  ПОТОКИ. Сокеты живут в своих потоках. Поток стратегии только кладёт строку в
//  очередь (Publish) и забирает команды (TryTakeCommand) — сеть его не держит.
//  Любое исключение сервера гасится внутри сервера: торговлю оно не останавливает.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public sealed class SwWsBridge
    {
        private const string Guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
        private readonly int port;
        private readonly string token;
        private readonly bool allowCommands;
        private readonly ConcurrentQueue<string> logs = new ConcurrentQueue<string>();
        private void log(string s) { if (logs.Count < 500) logs.Enqueue(s); }
        private TcpListener listener;
        private volatile bool running;
        private readonly List<Client> clients = new List<Client>();
        private readonly ConcurrentQueue<string> commands = new ConcurrentQueue<string>();

        private sealed class Client
        {
            public TcpClient Tcp; public NetworkStream Net; public bool Authed;
            public readonly ConcurrentQueue<string> Out = new ConcurrentQueue<string>();
            public DateTime LastCommand = DateTime.MinValue;
        }

        public SwWsBridge(int port, string tokenFile, bool allowCommands)
        {
            this.port = port; this.allowCommands = allowCommands;
            token = LoadOrCreateToken(tokenFile);
        }

        public static string LoadOrCreateToken(string path)
        {
            try
            {
                if (File.Exists(path)) { string t = File.ReadAllText(path).Trim(); if (t.Length >= 32) return t; }
                byte[] b = new byte[16]; using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b);
                string tok = BitConverter.ToString(b).Replace("-", "").ToLowerInvariant();
                Directory.CreateDirectory(Path.GetDirectoryName(path)); File.WriteAllText(path, tok);
                return tok;
            }
            catch { return Guid; }          // запасной ключ: сервер не падает из-за файла
        }

        public int ClientCount { get { lock (clients) return clients.Count; } }

        public void Start()
        {
            try
            {
                listener = new TcpListener(IPAddress.Loopback, port);
                listener.Start(); running = true;
                new Thread(AcceptLoop) { IsBackground = true, Name = "DZ_WS_Accept" }.Start();
                new Thread(SendLoop) { IsBackground = true, Name = "DZ_WS_Send" }.Start();
                log("сервер пульта: 127.0.0.1:" + port + (allowCommands ? ", команды разрешены" : ", только наблюдение"));
            }
            catch (Exception ex) { running = false; log("сервер пульта не запущен: " + ex.Message); }
        }

        public void Stop()
        {
            running = false;
            try { if (listener != null) listener.Stop(); } catch { }
            lock (clients) { foreach (Client c in clients) Close(c); clients.Clear(); }
        }

        /// <summary>Из потока стратегии: разослать всем вошедшим клиентам. Не ждёт сеть.</summary>
        public void Publish(string json)
        {
            if (!running) return;
            lock (clients)
                foreach (Client c in clients)
                    if (c.Authed) { c.Out.Enqueue(json); string drop; while (c.Out.Count > 200 && c.Out.TryDequeue(out drop)) { } }
        }

        /// <summary>Из потока стратегии: забрать запись журнала сервера — журнал коммутатора не потокобезопасен.</summary>
        public bool TryTakeLog(out string s) { return logs.TryDequeue(out s); }

        /// <summary>Из потока стратегии: забрать следующую разрешённую команду.</summary>
        public bool TryTakeCommand(out string cmd) { return commands.TryDequeue(out cmd); }

        private void AcceptLoop()
        {
            while (running)
            {
                try
                {
                    TcpClient tcp = listener.AcceptTcpClient();
                    lock (clients) if (clients.Count >= 4) { tcp.Close(); continue; }
                    new Thread(() => Serve(tcp)) { IsBackground = true, Name = "DZ_WS_Client" }.Start();
                }
                catch { if (!running) return; }
            }
        }

        private void Serve(TcpClient tcp)
        {
            Client c = new Client { Tcp = tcp };
            try
            {
                tcp.NoDelay = true; c.Net = tcp.GetStream();
                if (!Handshake(c.Net)) { tcp.Close(); return; }
                lock (clients) clients.Add(c);
                while (running)
                {
                    string msg = ReadFrame(c);
                    if (msg == null) break;
                    OnMessage(c, msg);
                }
            }
            catch { }
            finally { lock (clients) clients.Remove(c); Close(c); }
        }

        private bool Handshake(NetworkStream s)
        {
            s.ReadTimeout = 5000;
            var sb = new StringBuilder(); byte[] one = new byte[1];
            while (sb.Length < 8192)
            {
                if (s.Read(one, 0, 1) != 1) return false;
                sb.Append((char)one[0]);
                if (sb.Length >= 4 && sb.ToString(sb.Length - 4, 4) == "\r\n\r\n") break;
            }
            string req = sb.ToString(), key = Header(req, "Sec-WebSocket-Key"), origin = Header(req, "Origin");
            if (key == null || !req.StartsWith("GET ")) return false;
            if (origin != null && origin != "null" && !origin.StartsWith("file://") && !origin.StartsWith("app://atlas"))
            {
                log("отказ: чужой источник " + origin);
                byte[] deny = Encoding.ASCII.GetBytes("HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n");
                s.Write(deny, 0, deny.Length); return false;
            }
            string accept;
            using (SHA1 sha = SHA1.Create()) accept = Convert.ToBase64String(sha.ComputeHash(Encoding.ASCII.GetBytes(key + Guid)));
            byte[] resp = Encoding.ASCII.GetBytes("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                                                  + "Sec-WebSocket-Accept: " + accept + "\r\n\r\n");
            s.Write(resp, 0, resp.Length); s.ReadTimeout = Timeout.Infinite;
            return true;
        }

        private static string Header(string req, string name)
        {
            foreach (string line in req.Split(new[] { "\r\n" }, StringSplitOptions.None))
            {
                int i = line.IndexOf(':');
                if (i > 0 && string.Equals(line.Substring(0, i).Trim(), name, StringComparison.OrdinalIgnoreCase))
                    return line.Substring(i + 1).Trim();
            }
            return null;
        }

        /// <summary>Кадр клиента: обязательно с маской, без фрагментации, не больше 4 КБ.</summary>
        private string ReadFrame(Client c)
        {
            while (true)
            {
                byte[] h = ReadExact(c.Net, 2); if (h == null) return null;
                bool fin = (h[0] & 0x80) != 0; int op = h[0] & 0x0F; bool masked = (h[1] & 0x80) != 0; long len = h[1] & 0x7F;
                if (len == 126) { byte[] e = ReadExact(c.Net, 2); if (e == null) return null; len = (e[0] << 8) | e[1]; }
                else if (len == 127) return null;
                if (!fin || !masked || len > 4096) return null;
                byte[] mask = ReadExact(c.Net, 4); byte[] p = ReadExact(c.Net, (int)len);
                if (mask == null || p == null) return null;
                for (int i = 0; i < p.Length; i++) p[i] ^= mask[i % 4];
                if (op == 0x8) return null;                                   // закрытие
                if (op == 0x9) { Send(c, p, 0xA); continue; }                 // ping → pong
                if (op == 0x1) return Encoding.UTF8.GetString(p);
            }
        }

        private static byte[] ReadExact(NetworkStream s, int n)
        {
            byte[] b = new byte[n]; int got = 0;
            while (got < n) { int r = s.Read(b, got, n - got); if (r <= 0) return null; got += r; }
            return b;
        }

        private void OnMessage(Client c, string msg)
        {
            string cmd = Field(msg, "cmd"), tok = Field(msg, "token");
            if (!c.Authed)
            {
                if (cmd == "auth" && tok == token) { c.Authed = true; c.Out.Enqueue("{\"t\":\"auth\",\"ok\":true,\"commands\":" + (allowCommands ? "true" : "false") + "}"); }
                else { log("отказ: неверный ключ"); Close(c); }
                return;
            }
            if (cmd != "pause" && cmd != "resume" && cmd != "flatten") { c.Out.Enqueue("{\"t\":\"reject\",\"why\":\"неизвестная команда\"}"); return; }
            if (!allowCommands) { c.Out.Enqueue("{\"t\":\"reject\",\"why\":\"команды выключены в настройках стратегии [U03]\"}"); return; }
            if ((DateTime.UtcNow - c.LastCommand).TotalSeconds < 1) { c.Out.Enqueue("{\"t\":\"reject\",\"why\":\"не чаще раза в секунду\"}"); return; }
            c.LastCommand = DateTime.UtcNow;
            commands.Enqueue(cmd);
            c.Out.Enqueue("{\"t\":\"queued\",\"cmd\":\"" + cmd + "\"}");
        }

        /// <summary>Значение строкового поля "name":"value" — без библиотеки JSON: сообщения крошечные.</summary>
        private static string Field(string json, string name)
        {
            string k = "\"" + name + "\""; int i = json.IndexOf(k, StringComparison.Ordinal); if (i < 0) return null;
            i = json.IndexOf(':', i + k.Length); if (i < 0) return null;
            int a = json.IndexOf('"', i + 1); if (a < 0) return null;
            int b = json.IndexOf('"', a + 1); return b < 0 ? null : json.Substring(a + 1, b - a - 1);
        }

        private void SendLoop()
        {
            DateTime hb = DateTime.UtcNow;
            while (running)
            {
                Client[] snap; lock (clients) snap = clients.ToArray();
                bool beat = (DateTime.UtcNow - hb).TotalSeconds >= 2; if (beat) hb = DateTime.UtcNow;
                foreach (Client c in snap)
                {
                    try
                    {
                        if (beat && c.Authed) c.Out.Enqueue("{\"t\":\"hb\"}");
                        string m; while (c.Out.TryDequeue(out m)) Send(c, Encoding.UTF8.GetBytes(m), 0x1);
                    }
                    catch { Close(c); }
                }
                Thread.Sleep(20);
            }
        }

        private static void Send(Client c, byte[] payload, int opcode)
        {
            byte[] head;
            if (payload.Length < 126) head = new byte[] { (byte)(0x80 | opcode), (byte)payload.Length };
            else if (payload.Length <= 65535) head = new byte[] { (byte)(0x80 | opcode), 126, (byte)(payload.Length >> 8), (byte)payload.Length };
            else { head = new byte[10]; head[0] = (byte)(0x80 | opcode); head[1] = 127; long L = payload.Length; for (int i = 0; i < 8; i++) head[9 - i] = (byte)(L >> (8 * i)); }
            lock (c) { c.Net.Write(head, 0, head.Length); c.Net.Write(payload, 0, payload.Length); }
        }

        private static void Close(Client c) { try { if (c.Tcp != null) c.Tcp.Close(); } catch { } }
    }
}
