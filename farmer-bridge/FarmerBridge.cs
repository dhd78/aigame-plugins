using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using BepInEx;
using UnityEngine;

namespace FarmerBridge
{
    [BepInPlugin("local.farmerbridge", "Farmer Bridge", "0.1.4")]
    public class FarmerBridgePlugin : BaseUnityPlugin
    {
        private const int Port = 15800;
        private static readonly bool DebugEnabled = Environment.GetEnvironmentVariable("FARMERBRIDGE_DEBUG") == "1";
        private readonly ConcurrentQueue<Action> _mainQueue = new ConcurrentQueue<Action>();
        private TcpListener _listener;
        private Thread _serverThread;
        private volatile bool _running;

        private void Awake()
        {
            Logger.LogInfo("FarmerBridge awake");
            _running = true;
            _listener = new TcpListener(IPAddress.Loopback, Port);
            _listener.Start();
            _serverThread = new Thread(ServerLoop) { IsBackground = true, Name = "FarmerBridgeHTTP" };
            _serverThread.Start();
            Logger.LogInfo("FarmerBridge listening on 127.0.0.1:" + Port);
        }

        private void Update()
        {
            Action action;
            while (_mainQueue.TryDequeue(out action))
            {
                try { action(); }
                catch (Exception ex) { Logger.LogError("main queue: " + ex); }
            }
        }

        private void OnDestroy()
        {
            _running = false;
            try { if (_listener != null) _listener.Stop(); } catch { }
        }

        private string OnMain(Func<string> fn, int timeoutMs = 3000)
        {
            string result = null;
            Exception error = null;
            using (var done = new ManualResetEventSlim(false))
            {
                _mainQueue.Enqueue(() =>
                {
                    try { result = fn(); }
                    catch (Exception ex) { error = ex; }
                    finally { done.Set(); }
                });
                if (!done.Wait(timeoutMs)) return "{\"ok\":false,\"error\":\"main-thread-timeout\"}";
            }
            if (error != null)
                return "{\"ok\":false,\"error\":\"" + Json(error.GetType().Name + ": " + error.Message) + "\"}";
            return result ?? "{\"ok\":false,\"error\":\"null-result\"}";
        }

        private void ServerLoop()
        {
            while (_running)
            {
                TcpClient client = null;
                try
                {
                    client = _listener.AcceptTcpClient();
                    client.ReceiveTimeout = 5000;
                    client.SendTimeout = 5000;
                    using (var stream = client.GetStream())
                    {
                        var request = ReadRequest(stream);
                        var path = RequestPath(request);
                        var body = RequestBody(request);
                        var response = Route(path, body);
                        var bytes = Encoding.UTF8.GetBytes(response);
                        var head = Encoding.ASCII.GetBytes(
                            "HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n" +
                            "Content-Length: " + bytes.Length + "\r\nConnection: close\r\n\r\n");
                        stream.Write(head, 0, head.Length);
                        stream.Write(bytes, 0, bytes.Length);
                    }
                }
                catch (Exception ex)
                {
                    if (_running) Logger.LogWarning("http: " + ex.Message);
                }
                finally
                {
                    try { if (client != null) client.Close(); } catch { }
                }
            }
        }

        private static string ReadRequest(NetworkStream stream)
        {
            var ms = new MemoryStream();
            var buf = new byte[4096];
            int headerEnd = -1;
            int contentLength = 0;

            while (ms.Length < 1024 * 1024)
            {
                int n = stream.Read(buf, 0, buf.Length);
                if (n <= 0) break;
                ms.Write(buf, 0, n);
                var all = Encoding.ASCII.GetString(ms.ToArray());
                headerEnd = all.IndexOf("\r\n\r\n", StringComparison.Ordinal);
                if (headerEnd >= 0)
                {
                    contentLength = ParseContentLength(all.Substring(0, headerEnd));
                    break;
                }
            }
            if (headerEnd < 0) return Encoding.UTF8.GetString(ms.ToArray());

            long bodyStart = headerEnd + 4;
            while (ms.Length - bodyStart < contentLength && ms.Length < 1024 * 1024)
            {
                int n = stream.Read(buf, 0, buf.Length);
                if (n <= 0) break;
                ms.Write(buf, 0, n);
            }
            return Encoding.UTF8.GetString(ms.ToArray());
        }

        private static int ParseContentLength(string headers)
        {
            foreach (var line in headers.Split(new[] { "\r\n" }, StringSplitOptions.None))
            {
                if (!line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase)) continue;
                int value;
                if (int.TryParse(line.Substring(15).Trim(), out value)) return Math.Max(0, value);
            }
            return 0;
        }

        private static string RequestPath(string request)
        {
            int sp1 = request.IndexOf(' ');
            int sp2 = sp1 < 0 ? -1 : request.IndexOf(' ', sp1 + 1);
            if (sp1 < 0 || sp2 < 0) return "/";
            return request.Substring(sp1 + 1, sp2 - sp1 - 1);
        }

        private static string RequestBody(string request)
        {
            int i = request.IndexOf("\r\n\r\n", StringComparison.Ordinal);
            return i < 0 ? "" : request.Substring(i + 4);
        }

        private string Route(string path, string body)
        {
            if (path.StartsWith("/health", StringComparison.Ordinal))
                return "{\"ok\":true,\"bridge\":\"farmer-bridge\",\"version\":\"0.1.4\",\"port\":" + Port + "}";
            if (path.StartsWith("/state", StringComparison.Ordinal))
                return OnMain(StateJson);
            if (path.StartsWith("/grid", StringComparison.Ordinal))
                return OnMain(() => GridJson(path));
            if (path.StartsWith("/drones", StringComparison.Ordinal))
                return OnMain(DronesJson);
            if (path.StartsWith("/items", StringComparison.Ordinal))
                return OnMain(ItemsJson);
            if (path.StartsWith("/unlocks", StringComparison.Ordinal))
                return OnMain(UnlocksJson);
            if (path.StartsWith("/tech", StringComparison.Ordinal))
                return OnMain(TechJson);
            if (path.StartsWith("/buy", StringComparison.Ordinal))
                return OnMain(() => BuyUnlock(body));
            if (path.StartsWith("/files", StringComparison.Ordinal))
                return OnMain(FilesJson);
            if (path.StartsWith("/file", StringComparison.Ordinal))
                return OnMain(() => FileCreate(body));
            if (path.StartsWith("/doc", StringComparison.Ordinal))
                return OnMain(() => DocJson(path));
            if (path.StartsWith("/output", StringComparison.Ordinal))
                return OnMain(OutputJson);
            if (path.StartsWith("/execution", StringComparison.Ordinal))
                return OnMain(ExecutionJson);
            if (path.StartsWith("/save", StringComparison.Ordinal))
                return OnMain(SaveGame);
            if (path.StartsWith("/load", StringComparison.Ordinal))
                return OnMain(LoadGame);
            if (path.StartsWith("/start", StringComparison.Ordinal))
                return OnMain(() => StartGame(body));
            // DebugEndpointGuard: write-debug routes are opt-in.
            if (!DebugEnabled && (path.StartsWith("/add_item", StringComparison.Ordinal)
                || path.StartsWith("/set_drone", StringComparison.Ordinal)
                || path.StartsWith("/set_ground", StringComparison.Ordinal)
                || path.StartsWith("/set_entity", StringComparison.Ordinal)))
                return "{\"ok\":false,\"error\":\"debug-disabled\"}";
            if (path.StartsWith("/add_item", StringComparison.Ordinal))
                return OnMain(() => AddItem(body));
            if (path.StartsWith("/set_drone", StringComparison.Ordinal))
                return OnMain(() => SetDrone(body));
            if (path.StartsWith("/set_ground", StringComparison.Ordinal))
                return OnMain(() => SetGround(body));
            if (path.StartsWith("/set_entity", StringComparison.Ordinal))
                return OnMain(() => SetEntity(body));
            if (path.StartsWith("/code", StringComparison.Ordinal))
                return OnMain(() => SetCode(body));
            if (path.StartsWith("/run", StringComparison.Ordinal))
                return OnMain(() => RunCode(body));
            if (path.StartsWith("/stop", StringComparison.Ordinal))
                return OnMain(StopCode);
            if (path.StartsWith("/step", StringComparison.Ordinal))
                return OnMain(StepCode);
            return "{\"ok\":false,\"error\":\"not-found\"}";
        }

        private static string ExtractSource(string body)
        {
            if (string.IsNullOrEmpty(body)) return null;
            int key = body.IndexOf("\"source\"", StringComparison.Ordinal);
            if (key < 0) return body;
            int colon = body.IndexOf(':', key);
            if (colon < 0) return null;
            int quote = body.IndexOf('"', colon + 1);
            if (quote < 0) return null;
            var sb = new StringBuilder();
            for (int i = quote + 1; i < body.Length; i++)
            {
                char c = body[i];
                if (c == '"') return sb.ToString();
                if (c == '\\' && i + 1 < body.Length)
                {
                    char n = body[++i];
                    switch (n)
                    {
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'u':
                            if (i + 4 < body.Length)
                            {
                                int code;
                                if (int.TryParse(body.Substring(i + 1, 4),
                                        System.Globalization.NumberStyles.HexNumber, null, out code))
                                {
                                    sb.Append((char)code);
                                    i += 4;
                                }
                            }
                            break;
                        default: sb.Append(n); break;
                    }
                }
                else sb.Append(c);
            }
            return null;
        }

        private static Workspace CurrentWorkspace()
        {
            var main = MainInstance();
            return main == null ? null : main.workspace;
        }

        private static bool IsValidCodeFileName(string name)
        {
            if (string.IsNullOrEmpty(name) || name.Length > 32) return false;
            foreach (var c in name)
            {
                if (!(char.IsLetterOrDigit(c) || c == '_' || c == '-')) return false;
            }
            return true;
        }

        private static CodeWindow GetCodeWindow(string file, bool create)
        {
            var workspace = CurrentWorkspace();
            if (workspace == null) return null;
            if (string.IsNullOrEmpty(file)) file = "main";

            CodeWindow cw;
            if (workspace.codeWindows.TryGetValue(file, out cw) && cw != null)
            {
                Activate(workspace, cw);
                return cw;
            }
            if (!create) return null;

            workspace.OpenCodeWindow(file, "", Vector2.zero, Vector2.zero);
            if (!workspace.codeWindows.TryGetValue(file, out cw) || cw == null) return null;
            Activate(workspace, cw);
            return cw;
        }

        private static void Activate(Workspace workspace, CodeWindow cw)
        {
            if (workspace == null || cw == null) return;
            var win = cw.GetComponent<Window>();
            if (win != null) workspace.activeWindow = win;
        }

        private static string FilesJson()
        {
            var workspace = CurrentWorkspace();
            if (workspace == null) return "{\"ok\":false,\"error\":\"no-workspace\"}";
            var files = new List<string>(workspace.codeWindows.Keys);
            files.Sort(StringComparer.OrdinalIgnoreCase);
            var current = workspace.activeWindow == null ? "main" : workspace.activeWindow.windowName;
            var sb = new StringBuilder("{\"ok\":true,\"current\":\"" + Json(current ?? "main") + "\",\"files\":[");
            for (int i = 0; i < files.Count; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append("\"" + Json(files[i]) + "\"");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static string FileCreate(string body)
        {
            var name = StringField(body, "name");
            if (!IsValidCodeFileName(name))
                return "{\"ok\":false,\"error\":\"invalid-file-name\"}";
            var workspace = CurrentWorkspace();
            if (workspace == null) return "{\"ok\":false,\"error\":\"no-workspace\"}";
            bool existed = workspace.codeWindows.ContainsKey(name);
            var cw = GetCodeWindow(name, true);
            if (cw == null) return "{\"ok\":false,\"error\":\"cannot-create-window\"}";
            return "{\"ok\":true,\"file\":\"" + Json(name) + "\",\"created\":" +
                   (existed ? "false" : "true") + ",\"current\":\"" +
                   Json(workspace.activeWindow == null ? name : workspace.activeWindow.windowName) + "\"}";
        }

        private static string SetCode(string body)
        {
            var source = ExtractSource(body);
            if (source == null) return "{\"ok\":false,\"error\":\"missing-source\"}";
            source = source.TrimStart('\uFEFF');
            var file = StringField(body, "file");
            if (string.IsNullOrEmpty(file)) file = "main";
            if (!IsValidCodeFileName(file))
                return "{\"ok\":false,\"error\":\"invalid-file-name\"}";
            var cw = GetCodeWindow(file, true);
            if (cw == null) return "{\"ok\":false,\"error\":\"no-code-window\"}";

            var input = typeof(CodeWindow).GetProperty("CodeInput",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).GetValue(cw, null);
            if (input == null) return "{\"ok\":false,\"error\":\"no-code-input\"}";

            var prop = input.GetType().GetProperty("text",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (prop != null && prop.CanWrite) prop.SetValue(input, source, null);
            else
            {
                var field = input.GetType().GetField("text",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (field == null) return "{\"ok\":false,\"error\":\"no-text-field\"}";
                field.SetValue(input, source);
            }
            return "{\"ok\":true,\"file\":\"" + Json(cw.fileName ?? file) + "\",\"chars\":" + source.Length + "}";
        }

        private static string RunCode(string body)
        {
            var main = MainInstance();
            var file = StringField(body, "file");
            if (string.IsNullOrEmpty(file)) file = "main";
            if (!IsValidCodeFileName(file))
                return "{\"ok\":false,\"error\":\"invalid-file-name\"}";
            var cw = GetCodeWindow(file, false);
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            if (cw == null) return "{\"ok\":false,\"error\":\"no-code-window\"}";
            var node = cw.Parse();
            if (node == null) return "{\"ok\":false,\"error\":\"parse-null\"}";
            main.StartMainExecution(cw, node, false);
            return "{\"ok\":true,\"file\":\"" + Json(cw.fileName ?? file) + "\"}";
        }

        private static string StopCode()
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            main.StopMainExecution();
            return "{\"ok\":true,\"stopped\":true}";
        }

        private static string StepCode()
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            main.NextExecutionStep();
            return "{\"ok\":true,\"stepped\":true}";
        }

        private static string StringField(string body, string name)
        {
            int key = body.IndexOf("\"" + name + "\"", StringComparison.Ordinal);
            if (key < 0) return null;
            int colon = body.IndexOf(':', key);
            if (colon < 0) return null;
            int quote = body.IndexOf('"', colon + 1);
            if (quote < 0) return null;
            var sb = new StringBuilder();
            for (int i = quote + 1; i < body.Length; i++)
            {
                char c = body[i];
                if (c == '"') return sb.ToString();
                if (c == '\\' && i + 1 < body.Length)
                {
                    char n = body[++i];
                    if (n == 'n') sb.Append('\n');
                    else if (n == 'r') sb.Append('\r');
                    else if (n == 't') sb.Append('\t');
                    else if (n == '"') sb.Append('"');
                    else if (n == '\\') sb.Append('\\');
                    else if (n == 'u' && i + 4 < body.Length)
                    {
                        int code;
                        if (int.TryParse(body.Substring(i + 1, 4),
                                System.Globalization.NumberStyles.HexNumber, null, out code))
                        {
                            sb.Append((char)code);
                            i += 4;
                        }
                    }
                    else sb.Append(n);
                }
                else sb.Append(c);
            }
            return null;
        }

        private static int IntField(string body, string name, int fallback)
        {
            int key = body.IndexOf("\"" + name + "\"", StringComparison.Ordinal);
            if (key < 0) return fallback;
            int colon = body.IndexOf(':', key);
            if (colon < 0) return fallback;
            int start = colon + 1;
            while (start < body.Length && char.IsWhiteSpace(body[start])) start++;
            int end = start;
            while (end < body.Length && (char.IsDigit(body[end]) || body[end] == '-')) end++;
            int value;
            return int.TryParse(body.Substring(start, end - start), out value) ? value : fallback;
        }

        private static string AddItem(string body)
        {
            var farm = CurrentFarm();
            if (farm == null) return "{\"ok\":false,\"error\":\"no-farm\"}";
            var name = StringField(body, "name");
            if (string.IsNullOrEmpty(name)) return "{\"ok\":false,\"error\":\"missing-name\"}";
            int id = StringIds.GetItemId(name);
            if (id < 0) return "{\"ok\":false,\"error\":\"unknown-item\"}";
            var items = farm.Items;
            var array = items == null ? null : items.items;
            if (array == null) return "{\"ok\":false,\"error\":\"no-item-array\"}";
            int delta = IntField(body, "count", 1);
            array[id] = Math.Max(0, array[id] + delta);
            return "{\"ok\":true,\"name\":\"" + Json(name) + "\",\"count\":" + array[id].ToString("0.###") + "}";
        }

        private static string SetDrone(string body)
        {
            var farm = CurrentFarm();
            if (farm == null) return "{\"ok\":false,\"error\":\"no-farm\"}";
            var drone = farm.drones == null || farm.drones.Count == 0 ? null : farm.drones[0];
            if (drone == null) return "{\"ok\":false,\"error\":\"no-drone\"}";
            int x = IntField(body, "x", drone.pos.x);
            int y = IntField(body, "y", drone.pos.y);
            int z = IntField(body, "z", drone.depth);
            var world = farm.grid == null ? new Vector2Int(1, 1) : farm.grid.WorldSize;
            if (x < 0 || y < 0 || x >= world.x || y >= world.y)
                return "{\"ok\":false,\"error\":\"out-of-world\"}";
            drone.pos = new Vector2Int(x, y);
            drone.depth = z;
            return "{\"ok\":true,\"drone\":{\"x\":" + x + ",\"y\":" + y + ",\"z\":" + z + "}}";
        }

        private static string SetGround(string body)
        {
            var farm = CurrentFarm();
            var grid = farm == null ? null : farm.grid;
            if (grid == null) return "{\"ok\":false,\"error\":\"no-grid\"}";
            var name = StringField(body, "ground");
            if (string.IsNullOrEmpty(name)) return "{\"ok\":false,\"error\":\"missing-ground\"}";
            int x = IntField(body, "x", 0);
            int y = IntField(body, "y", 0);
            int depth = IntField(body, "depth", -1);
            if (x < 0 || y < 0 || x >= grid.WorldSize.x || y >= grid.WorldSize.y)
                return "{\"ok\":false,\"error\":\"out-of-world\"}";
            if (depth >= 0)
                grid.SetGround(new Vector3Int(x, y, depth), name);
            else
                grid.SetGround(new Vector2Int(x, y), name);
            return "{\"ok\":true,\"ground\":\"" + Json(name) + "\",\"x\":" + x + ",\"y\":" + y +
                   (depth >= 0 ? ",\"depth\":" + depth : "") + "}";
        }

        private static string SetEntity(string body)
        {
            var farm = CurrentFarm();
            var grid = farm == null ? null : farm.grid;
            if (grid == null) return "{\"ok\":false,\"error\":\"no-grid\"}";
            var name = StringField(body, "entity");
            if (string.IsNullOrEmpty(name)) return "{\"ok\":false,\"error\":\"missing-entity\"}";
            int x = IntField(body, "x", 0);
            int y = IntField(body, "y", 0);
            if (x < 0 || y < 0 || x >= grid.WorldSize.x || y >= grid.WorldSize.y)
                return "{\"ok\":false,\"error\":\"out-of-world\"}";
            grid.SetEntity(new Vector2Int(x, y), name);
            return "{\"ok\":true,\"entity\":\"" + Json(name) + "\",\"x\":" + x + ",\"y\":" + y + "}";
        }

        private static object StaticField(Type type, string name)
        {
            var f = type.GetField(name, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
            return f == null ? null : f.GetValue(null);
        }

        private static object InstanceField(object target, string name)
        {
            if (target == null) return null;
            var f = target.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            return f == null ? null : f.GetValue(target);
        }

        private static MainSim MainInstance()
        {
            return StaticField(typeof(MainSim), "_instance") as MainSim;
        }

        private static Simulation CurrentSim()
        {
            var main = MainInstance();
            var sim = InstanceField(main, "sim") as Simulation;
            if (sim != null) return sim;
            var ui = UISim.Inst;
            return InstanceField(ui, "sim") as Simulation;
        }

        private static Farm CurrentFarm()
        {
            var sim = CurrentSim();
            return sim == null ? null : sim.farm;
        }

        private static string StateJson()
        {
            var main = MainInstance();
            var ui = UISim.Inst;
            var sim = CurrentSim();
            var farm = sim == null ? null : sim.farm;
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true");
            sb.Append(",\"main\":" + (main != null ? "true" : "false"));
            sb.Append(",\"ui\":" + (ui != null ? "true" : "false"));
            sb.Append(",\"sim\":" + (sim != null ? "true" : "false"));
            if (sim != null)
            {
                sb.Append(",\"time\":" + sim.CurrentTime.Seconds.ToString("0.###"));
                sb.Append(",\"executing\":" + (sim.IsExecuting() ? "true" : "false"));
                sb.Append(",\"paused\":" + (sim.Paused ? "true" : "false"));
            }
            if (farm != null)
            {
                sb.Append(",\"farm\":" + FarmJson(farm));
            }
            sb.Append(",\"drones\":" + DronesJsonArray(farm));
            sb.Append(",\"items\":" + ItemsJsonArray(farm));
            sb.Append(",\"unlocks\":" + UnlocksJsonArray(farm));
            sb.Append("}");
            return sb.ToString();
        }

        private static string FarmJson(Farm farm)
        {
            var sb = new StringBuilder();
            sb.Append("{\"mainDroneId\":" + farm.mainDroneId);
            var dlc = farm.installedDlcs.ToString();
            if (dlc == "Minig") dlc = "Mining";
            else dlc = dlc.Replace("Minig", "Mining");
            sb.Append(",\"dlc\":\"" + Json(dlc) + "\"");
            var grid = farm.grid;
            if (grid != null)
            {
                sb.Append(",\"world\":[" + grid.WorldSize.x + "," + grid.WorldSize.y + "]");
                sb.Append(",\"maxUncoveredDepth\":" + grid.maxUncoveredDepth);
            }
            sb.Append("}");
            return sb.ToString();
        }

        private static string DronesJsonArray(Farm farm)
        {
            var sb = new StringBuilder("[");
            if (farm != null && farm.drones != null)
            {
                bool first = true;
                foreach (var drone in farm.drones)
                {
                    if (drone == null) continue;
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":" + drone.DroneId + ",\"x\":" + drone.pos.x + ",\"y\":" + drone.pos.y + ",\"z\":" + drone.depth + "}");
                }
            }
            sb.Append("]");
            return sb.ToString();
        }

        private static string DronesJson()
        {
            return "{\"ok\":true,\"drones\":" + DronesJsonArray(CurrentFarm()) + "}";
        }

        private static string ItemsJsonArray(Farm farm)
        {
            var sb = new StringBuilder("[");
            if (farm != null)
            {
                var items = farm.Items;
                var array = items == null ? null : items.items;
                if (array != null)
                {
                    bool first = true;
                    for (int i = 0; i < array.Length; i++)
                    {
                        if (array[i] == 0) continue;
                        if (!first) sb.Append(",");
                        first = false;
                        string name;
                        try { name = StringIds.GetItemName(i); }
                        catch { name = "item" + i; }
                        sb.Append("{\"id\":" + i + ",\"name\":\"" + Json(name) + "\",\"count\":" + array[i].ToString("0.###") + "}");
                    }
                }
            }
            sb.Append("]");
            return sb.ToString();
        }

        private static string ItemsJson()
        {
            return "{\"ok\":true,\"items\":" + ItemsJsonArray(CurrentFarm()) + "}";
        }

        private static string UnlocksJsonArray(Farm farm)
        {
            var sb = new StringBuilder("[");
            if (farm != null)
            {
                var dict = InstanceField(farm, "unlocks") as Dictionary<string, int>;
                if (dict != null)
                {
                    bool first = true;
                    foreach (var pair in dict)
                    {
                        if (!first) sb.Append(",");
                        first = false;
                        sb.Append("{\"name\":\"" + Json(pair.Key) + "\",\"level\":" + pair.Value + "}");
                    }
                }
            }
            sb.Append("]");
            return sb.ToString();
        }

        private static string UnlocksJson()
        {
            return "{\"ok\":true,\"unlocks\":" + UnlocksJsonArray(CurrentFarm()) + "}";
        }

        private static string TechJson()
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            var inventory = main.GetInventory();
            var current = main.GetUnlocks();
            var sb = new StringBuilder("{\"ok\":true,\"tech\":[");
            bool first = true;
            foreach (var unlock in ResourceManager.GetAllUnlocks())
            {
                if (unlock == null || !unlock.enabled) continue;
                if (!first) sb.Append(",");
                first = false;
                int level;
                current.TryGetValue(unlock.unlockName, out level);
                sb.Append("{\"name\":\"" + Json(unlock.unlockName ?? "") + "\"");
                sb.Append(",\"level\":" + level);
                sb.Append(",\"max\":" + unlock.maxUnlockLevel);
                sb.Append(",\"parent\":\"" + Json(unlock.parentUnlock ?? "") + "\"");
                sb.Append(",\"docs\":\"" + Json(unlock.docs ?? "") + "\"");
                sb.Append(",\"cost\":");
                AppendCost(sb, unlock.unlockCost);
                sb.Append(",\"nextCost\":");
                var farm = CurrentFarm();
                AppendCost(sb, farm == null ? null : farm.GetUnlockCost(unlock, level));
                bool installed = true;
                try { installed = farm == null || farm.IsDlcInstalled(unlock.dlc); }
                catch { installed = true; }
                sb.Append(",\"dlc\":\"" + Json(unlock.dlc.ToString()) + "\"");
                sb.Append(",\"installed\":" + (installed ? "true" : "false"));
                sb.Append("}");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static void AppendCost(StringBuilder sb, ItemBlock cost)
        {
            sb.Append("{");
            bool first = true;
            if (cost != null && cost.items != null)
            {
                for (int i = 0; i < cost.items.Length; i++)
                {
                    if (cost.items[i] <= 0) continue;
                    if (!first) sb.Append(",");
                    first = false;
                    string name;
                    try { name = StringIds.GetItemName(i); }
                    catch { name = "item" + i; }
                    sb.Append("\"" + Json(name) + "\":" + cost.items[i].ToString("0.###"));
                }
            }
            sb.Append("}");
        }

        private static string BuyUnlock(string body)
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            var name = StringField(body, "name");
            if (string.IsNullOrEmpty(name)) return "{\"ok\":false,\"error\":\"missing-name\"}";
            var unlock = ResourceManager.GetUnlockOf(name);
            if (unlock == null) return "{\"ok\":false,\"error\":\"unknown-unlock\"}";
            var sim = CurrentSim();
            bool executing = sim != null && sim.IsExecuting();
            var farm = CurrentFarm();
            int before = farm == null ? 0 : farm.NumUnlocked(unlock);
            bool bought = main.UnlockOrUpgrade(unlock);
            int after = farm == null ? before : farm.NumUnlocked(unlock);
            return "{\"ok\":true,\"name\":\"" + Json(unlock.unlockName ?? name) + "\",\"bought\":" +
                   (bought ? "true" : "false") + ",\"before\":" + before + ",\"after\":" + after +
                   ",\"executing\":" + (executing ? "true" : "false") + "}";
        }

        private static string DocJson(string path)
        {
            var page = QueryValue(path, "page");
            if (string.IsNullOrEmpty(page)) page = "docs/home.md";

            var windows = UnityEngine.Object.FindObjectsOfType<DocsWindow>();
            DocsWindow docs = windows.Length == 0 ? null : windows[0];
            if (docs == null)
            {
                var lang = string.IsNullOrEmpty(Localizer.Lang) ? "ZH" : Localizer.Lang;
                var file = Path.Combine(Application.streamingAssetsPath, "Languages", lang, page);
                if (File.Exists(file))
                    return "{\"ok\":true,\"page\":\"" + Json(page) + "\",\"source\":\"file\",\"text\":\"" +
                           Json(File.ReadAllText(file)) + "\"}";
                var main = MainInstance();
                if (main == null || main.workspace == null) return "{\"ok\":false,\"error\":\"no-workspace\"}";
                main.workspace.OpenDocsWindow("docs", page, Vector2.zero, Vector2.zero);
                windows = UnityEngine.Object.FindObjectsOfType<DocsWindow>();
                docs = windows.Length == 0 ? null : windows[0];
            }
            if (docs == null) return "{\"ok\":false,\"error\":\"no-docs-window\"}";

            docs.LoadDoc(page);
            return "{\"ok\":true,\"page\":\"" + Json(docs.openDoc ?? page) + "\",\"text\":\"" +
                   Json(docs.fullOpenDoc ?? "") + "\"}";
        }

        private static string QueryValue(string path, string key)
        {
            int q = path.IndexOf('?');
            if (q < 0) return null;
            foreach (var part in path.Substring(q + 1).Split('&'))
            {
                int eq = part.IndexOf('=');
                if (eq <= 0) continue;
                if (part.Substring(0, eq) == key) return Uri.UnescapeDataString(part.Substring(eq + 1));
            }
            return null;
        }

        private static string OutputJson()
        {
            var main = MainInstance();
            if (main == null || main.Logger == null) return "{\"ok\":false,\"error\":\"no-logger\"}";
            return "{\"ok\":true,\"output\":\"" + Json(main.Logger.GetOutputString()) + "\"}";
        }

        private static string ExecutionJson()
        {
            var sim = CurrentSim();
            var execution = sim == null ? null : sim.Execution;
            if (execution == null) return "{\"ok\":true,\"executing\":false}";
            var state = execution.MainState;
            return "{\"ok\":true,\"executing\":true,\"id\":" + execution.Id +
                   ",\"globalOps\":" + execution.GlobalOpCount.ToString("0.###") +
                   ",\"performingStep\":" + (execution.IsPerformingAStep ? "true" : "false") +
                   ",\"mainState\":" + (state == null ? "null" : "\"opCount=" + state.OpCount.ToString("0.###") + "\"") + "}";
        }

        private static string SaveGame()
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            Saver.Save(main);
            return "{\"ok\":true,\"queued\":true}";
        }

        private static string LoadGame()
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            try
            {
                main.StopMainExecution();
                Saver.Load(main);
                return "{\"ok\":true,\"loaded\":true}";
            }
            catch (Exception ex)
            {
                return "{\"ok\":false,\"error\":\"" + Json(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        private static string StartGame(string body)
        {
            var main = MainInstance();
            if (main == null) return "{\"ok\":false,\"error\":\"no-main-sim\"}";
            Menu menu = null;
            var menus = Resources.FindObjectsOfTypeAll<Menu>();
            for (int i = 0; i < menus.Length; i++)
            {
                if (menus[i] != null) { menu = menus[i]; break; }
            }
            if (menu == null) return "{\"ok\":false,\"error\":\"no-menu\"}";

            var save = StringField(body, "save");
            try
            {
                main.StopMainExecution();
                if (!string.IsNullOrEmpty(save))
                {
                    // Existing saves may contain non-ASCII names (for example Chinese).
                    // Reject path separators/traversal, but do not use IsValidSaveName here.
                    if (save.IndexOfAny(new[] { '/', '\\' }) >= 0 || save == "." || save == ".." ||
                        !Directory.Exists(Saver.GetPathOfSaveDirectory(save)))
                        return "{\"ok\":false,\"error\":\"save-not-found\"}";
                    menu.LoadSave(save);
                    Saver.Load(main);
                }
                menu.Play();
                return "{\"ok\":true,\"started\":true,\"save\":\"" +
                       Json(string.IsNullOrEmpty(save) ? "active" : save) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"ok\":false,\"error\":\"" + Json(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        private static string GridJson(string path)
        {
            var farm = CurrentFarm();
            var grid = farm == null ? null : farm.grid;
            if (grid == null) return "{\"ok\":false,\"error\":\"no-farm-grid\"}";

            int x = 0, y = 0, w = 8, h = 8, depth = -1;
            var query = path.IndexOf('?') >= 0 ? path.Substring(path.IndexOf('?') + 1) : "";
            foreach (var part in query.Split('&'))
            {
                var kv = part.Split('=');
                if (kv.Length != 2) continue;
                int v;
                if (!int.TryParse(kv[1], out v)) continue;
                if (kv[0] == "x") x = v;
                if (kv[0] == "y") y = v;
                if (kv[0] == "w") w = Mathf.Clamp(v, 1, 32);
                if (kv[0] == "h") h = Mathf.Clamp(v, 1, 32);
                if (kv[0] == "depth" || kv[0] == "z") depth = Mathf.Max(0, v);
            }

            var size = grid.WorldSize;
            var maxX = Mathf.Min(size.x, x + w);
            var maxY = Mathf.Min(size.y, y + h);
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true,\"world\":[" + size.x + "," + size.y + "]");
            sb.Append(",\"maxUncoveredDepth\":" + grid.maxUncoveredDepth);
            if (depth >= 0) sb.Append(",\"depth\":" + depth);
            sb.Append(",\"cells\":[");
            bool first = true;
            for (int cy = Mathf.Max(0, y); cy < maxY; cy++)
            {
                for (int cx = Mathf.Max(0, x); cx < maxX; cx++)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    if (depth < 0)
                    {
                        var cell = grid.cells[cy * size.x + cx];
                        sb.Append("{\"x\":" + cx + ",\"y\":" + cy + ",\"z\":" + cell.depth +
                                  ",\"entity\":\"" + Json(cell.entity == null ? "" : cell.entity.GetType().Name) + "\"" +
                                  ",\"water\":" + cell.waterVolume.ToString("0.###") +
                                  ",\"cactus\":" + cell.cactusNumber);
                        AppendEntityDetail(sb, cell.entity);
                        sb.Append("}");
                    }
                    else
                    {
                        GroundData.Ground ground;
                        bool present = grid.TryGetExistingGroundAt(new Vector3Int(cx, cy, depth), out ground);
                        sb.Append("{\"x\":" + cx + ",\"y\":" + cy + ",\"z\":" + depth +
                                  ",\"present\":" + (present ? "true" : "false"));
                        if (present)
                        {
                            string groundName = ground.groundSo == null ? "" : ground.groundSo.objectName;
                            sb.Append(",\"ground\":\"" + Json(groundName) + "\"");
                            sb.Append(",\"hardness\":" + ground.hardness);
                            sb.Append(",\"stability\":" + ground.stability);
                        }
                        sb.Append("}");
                    }
                }
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static void AppendEntityDetail(StringBuilder sb, Entity entity)
        {
            if (entity == null) return;
            var so = entity.objectSO;
            sb.Append(",\"name\":\"" + Json(so == null ? "" : so.objectName) + "\"");
            var growable = entity as Growable;
            if (growable == null) return;
            sb.Append(",\"grown\":" + (growable.Harvestable ? "true" : "false"));
            var pct = growable.GrownPercent;
            if (pct < 0) pct = 0;
            if (pct > 1) pct = 1;
            sb.Append(",\"growPct\":" + pct.ToString("0.###"));
            var companionType = InstanceField(growable, "companionType") as EntitySO;
            var companionPosObj = InstanceField(growable, "companionPos");
            if (companionType != null && companionPosObj is Vector2Int)
            {
                var pos = (Vector2Int)companionPosObj;
                sb.Append(",\"companion\":{\"name\":\"" + Json(companionType.objectName) + "\",\"x\":" +
                          pos.x + ",\"y\":" + pos.y + "}");
            }
        }

        private static string Json(string value)
        {
            if (value == null) return "";
            var sb = new StringBuilder(value.Length + 8);
            foreach (var c in value)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u" + ((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.ToString();
        }
    }
}

