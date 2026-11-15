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
using UnityEngine.UI;

namespace VolcanoBridge
{
    [BepInPlugin("local.volcanobridge", "Volcano Bridge", "0.1.9")]
    public class VolcanoBridge : BaseUnityPlugin
    {
        private const int Port = 15801;
        private TcpListener listener;
        private Thread serverThread;
        private volatile bool running;
        private readonly ConcurrentQueue<Action> mainQueue = new ConcurrentQueue<Action>();

        private void Awake()
        {
            try
            {
                listener = new TcpListener(IPAddress.Loopback, Port);
                listener.Start();
                running = true;
                serverThread = new Thread(ServerLoop);
                serverThread.IsBackground = true;
                serverThread.Start();
                Logger.LogInfo("VolcanoBridge listening on 127.0.0.1:" + Port);
            }
            catch (Exception ex)
            {
                Logger.LogError("VolcanoBridge start failed: " + ex);
            }
        }

        private void Update()
        {
            Action action;
            while (mainQueue.TryDequeue(out action))
            {
                try { action(); }
                catch (Exception ex) { Logger.LogError("main queue: " + ex); }
            }
        }

        private void OnDestroy()
        {
            running = false;
            try { if (listener != null) listener.Stop(); } catch { }
        }

        private void ServerLoop()
        {
            while (running)
            {
                try
                {
                    var client = listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(delegate { HandleClient(client); });
                }
                catch (Exception)
                {
                    if (!running) return;
                }
            }
        }

        private void HandleClient(TcpClient client)
        {
            try
            {
                using (client)
                using (var stream = client.GetStream())
                {
                    var reader = new StreamReader(stream, Encoding.ASCII, false, 1024, true);
                    string requestLine = reader.ReadLine();
                    if (string.IsNullOrEmpty(requestLine)) return;
                    string[] parts = requestLine.Split(' ');
                    string path = parts.Length > 1 ? parts[1] : "/";
                    string rawPath = path;
                    int query = path.IndexOf('?');
                    if (query >= 0) path = path.Substring(0, query);
                    string body;
                    if (path == "/health")
                    {
                        body = "{\"ok\":true,\"bridge\":\"volcano-bridge\",\"version\":\"0.1.9\",\"port\":" + Port + "}";
                    }
                    else if (path == "/state")
                    {
                        body = OnMain(StateJson);
                    }
                    else if (path == "/load")
                    {
                        body = OnMain(delegate { return LoadJson(rawPath); });
                    }
                    else if (path == "/savedata")
                    {
                        body = SavedataJson(rawPath);
                    }
                    else if (path == "/ui")
                    {
                        body = OnMain(UiJson);
                    }
                    else if (path == "/chat")
                    {
                        body = OnMain(ChatJson);
                    }
                    else if (path == "/advance" || path == "/next")
                    {
                        body = OnMain(delegate { return AdvanceJson(rawPath); });
                    }
                    else if (path == "/choose")
                    {
                        body = OnMain(delegate { return ChooseJson(rawPath); });
                    }
                    else if (path == "/wish")
                    {
                        body = OnMain(delegate { return WishJson(rawPath); });
                    }
                    else if (path == "/click")
                    {
                        body = OnMain(delegate { return ClickJson(rawPath); });
                    }
                    else if (path == "/uibtn")
                    {
                        body = OnMain(delegate { return UiBtnJson(rawPath); });
                    }
                    else if (path == "/talentinfo")
                    {
                        body = OnMain(delegate { return TalentInfoJson(rawPath); });
                    }
                    else if (path == "/nextday" || path == "/endturn")
                    {
                        body = OnMain(delegate { return NextDayJson(rawPath); });
                    }
                    else if (path == "/resnpc")
                    {
                        body = OnMain(delegate { return ResNpcJson(rawPath); });
                    }
                    else
                    {
                        body = "{\"ok\":false,\"error\":\"not-found\"}";
                    }
                    WriteResponse(stream, body);
                }
            }
            catch (Exception)
            {
            }
        }

        private static string OnMain(Func<string> func)
        {
            // The server is always hosted by the plugin instance; use the
            // static queue through a captured delegate-free path.
            var bridge = UnityEngine.Object.FindObjectOfType<VolcanoBridge>();
            if (bridge == null) return "{\"ok\":false,\"error\":\"no-bridge\"}";
            string result = null;
            Exception error = null;
            var done = new ManualResetEventSlim(false);
            bridge.mainQueue.Enqueue(delegate
            {
                try { result = func(); }
                catch (Exception ex) { error = ex; }
                finally { done.Set(); }
            });
            if (!done.Wait(5000)) return "{\"ok\":false,\"error\":\"timeout\"}";
            if (error != null) return "{\"ok\":false,\"error\":\"" + Json(error.GetType().Name + ": " + error.Message) + "\"}";
            return result;
        }

        private static void WriteResponse(Stream stream, string body)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(body ?? "");
            string header = "HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: " +
                            bytes.Length + "\r\nConnection: close\r\n\r\n";
            byte[] head = Encoding.ASCII.GetBytes(header);
            stream.Write(head, 0, head.Length);
            stream.Write(bytes, 0, bytes.Length);
            stream.Flush();
        }

        private sealed class ModalInfo
        {
            public string Kind = "";
            public string RootPath = "";
            public Transform Root;
            public bool Blocking;
        }

        private static bool FindActiveExact(string path, out Transform transform)
        {
            transform = null;
            var go = GameObject.Find(path);
            if (go == null || !go.activeInHierarchy) return false;
            transform = go.transform;
            return true;
        }

        private static bool FindActiveContains(string needle, out Transform transform)
        {
            transform = null;
            string bestPath = null;
            var all = UnityEngine.Object.FindObjectsOfType<Transform>();
            for (int i = 0; i < all.Length; i++)
            {
                var item = all[i];
                if (item == null || !item.gameObject.activeInHierarchy) continue;
                string path = PathOf(item);
                if (path.IndexOf(needle, StringComparison.OrdinalIgnoreCase) < 0) continue;
                if (bestPath == null || path.Length < bestPath.Length)
                {
                    bestPath = path;
                    transform = item;
                }
            }
            return transform != null;
        }

        private static ModalInfo GetModal()
        {
            var modal = new ModalInfo();
            Transform root;

            // Father-type review cards are instantiated at runtime (TaskSys.faReviewTs)
            // and do not have a stable static path.
            if (TaskSys.Instan != null)
            {
                var field = typeof(TaskSys).GetField("faReviewTs",
                    BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                var review = field == null ? null : field.GetValue(TaskSys.Instan) as Transform;
                if (review != null && review.gameObject.activeInHierarchy)
                {
                    modal.Kind = "fatherWish";
                    modal.Root = review;
                    modal.RootPath = PathOf(review);
                    modal.Blocking = true;
                    return modal;
                }
            }

            // Priority: specific event/modal windows before the general chat layer.
            if (FindActiveExact("UI/49 TipUi/070 worryChoice(Clone)", out root) ||
                FindActiveContains("070 worryChoice", out root))
            {
                modal.Kind = "worryChoice";
            }
            else if (FindActiveExact("UI/49 TipUi/14Chat", out root) ||
                     FindActiveContains("TipUi/14Chat", out root))
            {
                // A chat/story layer can sit on top of stage-summary processing.
                modal.Kind = "chat";
            }
            else if (FindActiveExact("UI/UI/showUi/17 阶段总结", out root) ||
                     FindActiveContains("17 阶段总结", out root) ||
                     FindActiveExact("UI/UI/TopShowUi/3processing", out root) ||
                     FindActiveContains("TopShowUi/3processing", out root))
            {
                modal.Kind = "stageSummary";
            }
            else if (FindActiveExact("UI/49 TipUi/16sureTip", out root) ||
                     FindActiveContains("16sureTip", out root))
            {
                modal.Kind = "sureTip";
            }
            else if (FindActiveExact("UI/UI/TopWnd/4按钮", out root) ||
                     FindActiveContains("TopWnd/4按钮", out root))
            {
                modal.Kind = "choice";
            }
            else if (FindActiveExact("UI/UI/36 TopWnd/50 父亲心愿", out root) ||
                     FindActiveContains("50 父亲心愿", out root))
            {
                modal.Kind = "fatherWish";
            }
            else if (FindActiveExact("UI/UI/TopShowUi/1plan", out root) ||
                     FindActiveContains("TopShowUi/1plan", out root))
            {
                modal.Kind = "plan";
                modal.Root = root;
                modal.RootPath = PathOf(root);
                modal.Blocking = false;
                return modal;
            }
            else
            {
                return modal;
            }

            modal.Root = root;
            modal.RootPath = PathOf(root);
            modal.Blocking = true;
            return modal;
        }

        private static bool IsInsideModal(string targetPath, ModalInfo modal)
        {
            if (string.IsNullOrEmpty(targetPath) || string.IsNullOrEmpty(modal.RootPath)) return false;
            return targetPath == modal.RootPath ||
                   targetPath.StartsWith(modal.RootPath + "/", StringComparison.Ordinal);
        }

        private static bool HasForce(string path)
        {
            if (string.IsNullOrEmpty(path)) return false;
            int q = path.IndexOf('?');
            if (q < 0) return false;
            string[] parts = path.Substring(q + 1).Split('&');
            foreach (string part in parts)
            {
                string[] kv = part.Split('=');
                if (kv.Length == 2 && kv[0] == "force" && kv[1] == "1") return true;
            }
            return false;
        }

        private static string QueryValue(string path, string key)
        {
            if (string.IsNullOrEmpty(path)) return null;
            int q = path.IndexOf('?');
            if (q < 0) return null;
            string[] parts = path.Substring(q + 1).Split('&');
            foreach (string part in parts)
            {
                string[] kv = part.Split('=');
                if (kv.Length == 2 && kv[0] == key) return Uri.UnescapeDataString(kv[1]);
            }
            return null;
        }

        private static string ModalChoicesJson(Transform root)
        {
            var sb = new StringBuilder();
            var seen = new HashSet<string>();
            var buttons = root.GetComponentsInChildren<Button>(true);
            var uiButtons = root.GetComponentsInChildren<UiBtn>(true);
            int index = 0;
            for (int i = 0; i < buttons.Length; i++)
            {
                var button = buttons[i];
                if (button == null || !button.gameObject.activeInHierarchy) continue;
                string path = PathOf(button.transform);
                if (!seen.Add(path)) continue;
                var label = button.GetComponentInChildren<Text>();
                if (index > 0) sb.Append(",");
                sb.Append("{\"index\":" + index + ",\"kind\":\"button\",\"text\":\"" +
                          Json(label == null ? "" : label.text) + "\",\"path\":\"" + Json(path) + "\"}");
                index++;
            }
            for (int i = 0; i < uiButtons.Length; i++)
            {
                var uiButton = uiButtons[i];
                if (uiButton == null || !uiButton.gameObject.activeInHierarchy) continue;
                string path = PathOf(uiButton.transform);
                if (!seen.Add(path)) continue;
                var label = uiButton.GetComponentInChildren<Text>();
                if (index > 0) sb.Append(",");
                sb.Append("{\"index\":" + index + ",\"kind\":\"uibutton\",\"text\":\"" +
                          Json(label == null ? "" : label.text) + "\",\"path\":\"" + Json(path) + "\"}");
                index++;
            }
            return "[" + sb.ToString() + "]";
        }

        private static void AppendModalJson(StringBuilder sb, ModalInfo modal)
        {
            sb.Append(",\"busy\":" + (modal.Blocking ? "true" : "false"));
            sb.Append(",\"modal\":\"" + Json(modal.Kind) + "\"");
            if (modal.Blocking && modal.Root != null)
                sb.Append(",\"modalChoices\":" + ModalChoicesJson(modal.Root));
        }

        private static bool IsForbiddenAction(string path, string label)
        {
            if (!string.IsNullOrEmpty(label) &&
                (label.Contains("跳过") || label.Contains("关闭剧情")))
                return true;
            if (string.IsNullOrEmpty(path)) return false;
            if (path.IndexOf("14Chat/bg", StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if (path.IndexOf("50 父亲心愿/bg", StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if (path.IndexOf("worryChoice", StringComparison.OrdinalIgnoreCase) >= 0 &&
                path.EndsWith("/bg", StringComparison.OrdinalIgnoreCase)) return true;
            if (path.IndexOf("4按钮/panel/choice/cells/002leaveBtn", StringComparison.OrdinalIgnoreCase) >= 0)
                return true;
            // The result page's "进入下月" is the normal month-end action,
            // not a skip. It exists only after the summary has been shown.
            if (path.IndexOf("3processing/panel/result/nextBtn", StringComparison.OrdinalIgnoreCase) >= 0)
                return false;
            return false;
        }

        private static string DisabledJson(string reason)
        {
            return "{\"ok\":false,\"error\":\"disabled\",\"reason\":\"" + Json(reason) + "\"}";
        }

        private static string BusyJson(ModalInfo modal)
        {
            return "{\"ok\":false,\"error\":\"busy\",\"modal\":\"" + Json(modal.Kind) +
                   "\",\"busy\":true}";
        }

        private static string StateJson()
        {
            var gm = GameManager.Instan;
            if (gm == null || DataSys.Instan == null)
                return "{\"ok\":false,\"error\":\"no-game\"}";

            var sb = new StringBuilder();
            sb.Append("{\"ok\":true");
            sb.Append(",\"turn\":" + DataSys.Turn());
            sb.Append(",\"coin\":" + DataSys.Coin());
            sb.Append(",\"energy\":" + DataSys.energy);
            sb.Append(",\"maxEnergy\":" + DataSys.MaxEnergy());
            sb.Append(",\"stage\":" + DataSys.Stage());
            sb.Append(",\"month\":" + DataSys.Month());
            sb.Append(",\"year\":\"" + Json(DataSys.Year()) + "\"");

            var dau = DauSys.Instan;
            if (dau != null)
            {
                sb.Append(",\"dau\":{");
                sb.Append("\"name\":\"" + Json(DauSys.DauName()) + "\"");
                sb.Append(",\"birth\":" + dau.birth);
                sb.Append(",\"blood\":" + dau.blood);
                sb.Append(",\"height\":" + dau.height.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture));
                sb.Append(",\"stage\":" + DauSys.DauStage());
                sb.Append(",\"age\":" + DauSys.Age());
                sb.Append(",\"mood\":" + DauSys.Mood());
                sb.Append(",\"darkness\":" + DauSys.Darkness());
                sb.Append(",\"fame\":" + DauSys.Fame());
                sb.Append(",\"motivation\":" + DauSys.Motivation());
                sb.Append(",\"inspiration\":" + DauSys.Inspiration());
                sb.Append(",\"favorLevel\":" + DauSys.favorLevel);
                sb.Append(",\"favor\":" + dau.favor);
                sb.Append(",\"nature\":" + IntArray(DauSys.NatureNums()));
                sb.Append(",\"natureLevel\":" + IntArray(DauSys.NatureLevels()));
                sb.Append(",\"inAttri\":" + IntArray(DauSys.InAttriNums()));
                sb.Append("}");
            }

            var courses = CourseSys.Instan;
            if (courses != null)
            {
                sb.Append(",\"courses\":{");
                sb.Append("\"finished\":" + StringList(courses.finishedCourses));
                sb.Append("}");
            }

            var map = MapSys.Instan;
            if (map != null)
            {
                sb.Append(",\"map\":{");
                sb.Append("\"workLevel\":" + map.workLevel);
                sb.Append("}");
            }

            var chat = ChatSys.Instan;
            if (chat != null)
            {
                sb.Append(",\"chat\":{");
                sb.Append("\"queue\":" + ChatSys.chatQueue.Count);
                sb.Append(",\"showing\":" + (Field(chat, "showingChat") is bool && (bool)Field(chat, "showingChat") ? "true" : "false"));
                sb.Append("}");
            }

            var modal = GetModal();
            AppendModalJson(sb, modal);
            sb.Append("}");
            return sb.ToString();
        }

        private static string SavedataJson(string path)
        {
            int index = 0;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length == 2 && (kv[0] == "index" || kv[0] == "slot"))
                        int.TryParse(kv[1], out index);
                }
            }
            var data = SaveSys.LoadArchiveData(index);
            if (data == null) return "{\"ok\":false,\"error\":\"save-not-found\",\"slot\":" + index + "}";
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true,\"slot\":" + index);
            sb.Append(",\"turn\":" + data.turn);
            sb.Append(",\"coin\":" + data.coin);
            sb.Append(",\"maxEnergy\":" + data.maxEnergy);
            sb.Append(",\"dauName\":\"" + Json(data.dauName) + "\"");
            sb.Append(",\"birth\":" + data.birth);
            sb.Append(",\"blood\":" + data.blood);
            sb.Append(",\"height\":" + data.height.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture));
            sb.Append(",\"mood\":" + data.mood);
            sb.Append(",\"moral\":" + data.moral);
            sb.Append(",\"fame\":" + data.fame);
            sb.Append(",\"motivation\":" + data.motivation);
            sb.Append(",\"inspiration\":" + data.inspiration);
            sb.Append(",\"favor\":" + data.favor);
            sb.Append(",\"nature\":" + IntArray(data.nature));
            sb.Append(",\"natureLevel\":" + IntArray(data.natureLevel));
            sb.Append(",\"inAttri\":" + IntArray(data.inAttri));
            sb.Append(",\"workLevel\":" + data.workLevel);
            sb.Append(",\"finishedCourses\":" + StringList(data.finishedCourses));
            sb.Append("}");
            return sb.ToString();
        }

        private static string LoadJson(string path)
        {
            return DisabledJson("load-disabled-use-manual-ui");
            int index = 0;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length == 2 && (kv[0] == "index" || kv[0] == "slot"))
                        int.TryParse(kv[1], out index);
                }
            }
            var gm = GameManager.Instan;
            if (gm == null) return "{\"ok\":false,\"error\":\"no-game\"}";
            var save = gm.GetComponent<SaveSys>();
            if (save == null) return "{\"ok\":false,\"error\":\"no-save-sys\"}";
            bool loaded = save.LoadGame(index);
            return "{\"ok\":" + (loaded ? "true" : "false") + ",\"loaded\":" + (loaded ? "true" : "false") +
                   ",\"slot\":" + index + "}";
        }

        private static string ChatJson()
        {
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true");
            var list = StaticField(typeof(ChatSys), "tempChat") as System.Collections.IList;
            sb.Append(",\"count\":" + (list == null ? 0 : list.Count));
            sb.Append(",\"showing\":" + (ChatSys.Instan != null &&
                Field(ChatSys.Instan, "showingChat") is bool && (bool)Field(ChatSys.Instan, "showingChat") ? "true" : "false"));
            sb.Append(",\"entries\":[");
            bool first = true;
            if (list != null)
            {
                for (int i = 0; i < list.Count; i++)
                {
                    var chat = list[i] as Chat;
                    if (chat == null) continue;
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"index\":" + i);
                    sb.Append(",\"name\":\"" + Json(chat.name) + "\"");
                    sb.Append(",\"icon\":\"" + Json(chat.icon) + "\"");
                    sb.Append(",\"voice\":\"" + Json(chat.voice) + "\"");
                    sb.Append(",\"type\":\"" + Json(chat.type) + "\"");
                    string text = ChatText(chat.content);
                    sb.Append(",\"content\":\"" + Json(chat.content) + "\"");
                    sb.Append(",\"text\":\"" + Json(text) + "\"");
                    if (!string.IsNullOrEmpty(text) && text.Contains("&") && IsChoiceChat(chat))
                    {
                        string[] options = text.Split('&');
                        sb.Append(",\"options\":[");
                        for (int j = 0; j < options.Length; j++)
                        {
                            if (j > 0) sb.Append(",");
                            sb.Append("\"" + Json(options[j]) + "\"");
                        }
                        sb.Append("]");
                    }
                    sb.Append("}");
                }
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static string ChatText(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            try
            {
                string text = ChatSys.Txt(value);
                return string.IsNullOrEmpty(text) ? value : text;
            }
            catch
            {
                return value;
            }
        }

        private static bool IsChoiceChat(Chat chat)
        {
            if (chat == null || string.IsNullOrEmpty(chat.name)) return false;
            string n = chat.name;
            return n == "select" || n == "wishChoice" || n == "worryChoice" ||
                   n == "birthdayChoice" || n == "faBirthChoice" || n == "logSelect" ||
                   n == "npcSelect" || n == "fightSelect" || n == "typeLogBtn" ||
                   n == "paitingType" || n == "springType" || n == "villageTalk" ||
                   n == "perMenu" || n == "schoolBallPartner" || n == "chooseStory";
        }

        private static string AdvanceJson(string path)
        {
            var modal = GetModal();
            if (modal.Blocking && modal.Kind != "chat" && !HasForce(path))
                return BusyJson(modal);
            if (ChatSys.Instan == null) return "{\"ok\":false,\"error\":\"no-chat\"}";
            var list = StaticField(typeof(ChatSys), "tempChat") as System.Collections.IList;
            if (list != null && list.Count > 0)
            {
                var current = list[0] as Chat;
                if (current != null)
                {
                    string currentText = ChatText(current.content);
                    if (IsChoiceChat(current))
                        return "{\"ok\":false,\"error\":\"choice-pending\"}";
                }
            }
            ChatSys.Instan.ClickToNextChat();
            return "{\"ok\":true,\"advanced\":true}";
        }

        private static string WishJson(string path)
        {
            return DisabledJson("wish-shortcut-disabled");
            var modal = GetModal();
            if (modal.Blocking && modal.Kind != "fatherWish" && !HasForce(path))
                return BusyJson(modal);
            int index = -1;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length == 2 && kv[0] == "index") int.TryParse(kv[1], out index);
                }
            }
            if (index < 0) return "{\"ok\":false,\"error\":\"missing-index\"}";
            if (TaskSys.Instan == null) return "{\"ok\":false,\"error\":\"no-task-sys\"}";
            TaskSys.Instan.EnterDauWishChoice(index);
            TaskSys.Instan.ChooseDauWish(index);
            return "{\"ok\":true,\"wish\":" + index + "}";
        }

        private static bool ChoiceMenuOpen()
        {
            var menu = GameObject.Find("UI/49 TipUi/14Chat/chat/menu");
            if (menu == null || !menu.activeInHierarchy) return false;
            var stateField = typeof(ChatSys).GetField("menuState",
                BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            var state = stateField == null ? null : stateField.GetValue(null);
            if (state == null) return false;
            // The visible menu can be left active for one frame while the
            // menu state is still normal. ClickMenuChoice in that window
            // ends the chat without selecting anything.
            return state.ToString() != "normal";
        }

        private static string ChooseJson(string path)
        {
            var modal = GetModal();
            if (modal.Blocking && modal.Kind != "chat" && !HasForce(path))
                return BusyJson(modal);
            int index = -1;
            string optionName = null;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length != 2) continue;
                    if (kv[0] == "index") int.TryParse(kv[1], out index);
                    if (kv[0] == "name") optionName = Uri.UnescapeDataString(kv[1]);
                }
            }
            if (index < 0) return "{\"ok\":false,\"error\":\"missing-index\"}";
            var list = StaticField(typeof(ChatSys), "tempChat") as System.Collections.IList;
            if (list == null || list.Count == 0) return "{\"ok\":false,\"error\":\"no-chat\"}";
            Chat select = null;
            for (int i = 0; i < list.Count; i++)
            {
                var chat = list[i] as Chat;
                if (chat != null && IsChoiceChat(chat))
                {
                    select = chat;
                    break;
                }
            }
            if (select == null)
                return "{\"ok\":false,\"error\":\"no-choice\"}";
            // wishChoice can be in tempChat a fraction before CallWishMenu
            // actually opens the clickable menu. Calling ClickMenuChoice here
            // would EndChat and skip the event.
            if (!ChoiceMenuOpen())
                return "{\"ok\":false,\"error\":\"choice-not-ready\",\"retryMs\":200}";
            if (select.name == "wishChoice")
            {
                if (TaskSys.Instan == null) return "{\"ok\":false,\"error\":\"no-task-sys\"}";
                // ClickMenuChoice performs the menu close/EndChat sequence before
                // dispatching to TaskSys.ChooseWishPerChoice. Calling the latter
                // directly leaves the old wishChoice entry in tempChat.
                ChatSys.Instan.ClickMenuChoice(index.ToString());
                return "{\"ok\":true,\"index\":" + index + ",\"name\":\"wishPer\"}";
            }
            string chooseName = select.icon + "#" + index;
            ChatSys.Instan.ClickMenuChoice(chooseName);
            return "{\"ok\":true,\"index\":" + index + ",\"name\":\"" + Json(chooseName) + "\"}";
        }

        private static object StaticField(Type type, string name)
        {
            var field = type.GetField(name, BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            return field == null ? null : field.GetValue(null);
        }

        private static string UiJson()
        {
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true");
            var modal = GetModal();
            sb.Append(",\"busy\":" + (modal.Blocking ? "true" : "false"));
            sb.Append(",\"modal\":\"" + Json(modal.Kind) + "\"");
            if (modal.Blocking && modal.Root != null)
                sb.Append(",\"modalButtons\":" + ModalChoicesJson(modal.Root));
            var texts = UnityEngine.Object.FindObjectsOfType<Text>();
            sb.Append(",\"texts\":[");
            bool first = true;
            for (int i = 0; i < texts.Length; i++)
            {
                var text = texts[i];
                if (text == null || !text.gameObject.activeInHierarchy || string.IsNullOrEmpty(text.text)) continue;
                if (!first) sb.Append(",");
                first = false;
                sb.Append("{\"text\":\"" + Json(text.text) + "\",\"path\":\"" + Json(PathOf(text.transform)) + "\"}");
            }
            sb.Append("]");

            var buttons = UnityEngine.Object.FindObjectsOfType<Button>();
            sb.Append(",\"buttons\":[");
            first = true;
            int index = 0;
            for (int i = 0; i < buttons.Length; i++)
            {
                var button = buttons[i];
                if (button == null || !button.gameObject.activeInHierarchy) continue;
                var label = button.GetComponentInChildren<Text>();
                if (!first) sb.Append(",");
                first = false;
                sb.Append("{\"index\":" + index + ",\"label\":\"" +
                          Json(label == null ? "" : label.text) + "\",\"path\":\"" +
                          Json(PathOf(button.transform)) + "\"}");
                index++;
            }
            sb.Append("]");

            var uiButtons = UnityEngine.Object.FindObjectsOfType<UiBtn>();
            sb.Append(",\"uibuttons\":[");
            first = true;
            for (int i = 0; i < uiButtons.Length; i++)
            {
                var uiButton = uiButtons[i];
                if (uiButton == null || !uiButton.gameObject.activeInHierarchy) continue;
                if (!first) sb.Append(",");
                first = false;
                sb.Append("{\"type\":\"" + Json(uiButton.type.ToString()) + "\",\"index\":" +
                          uiButton.index + ",\"path\":\"" + Json(PathOf(uiButton.transform)) + "\"}");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static string ResNpcJson(string path)
        {
            var modal = GetModal();
            if (modal.Blocking && !HasForce(path)) return BusyJson(modal);
            string name = null;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length == 2 && kv[0] == "name") name = Uri.UnescapeDataString(kv[1]);
                }
            }
            if (string.IsNullOrEmpty(name)) return "{\"ok\":false,\"error\":\"missing-name\"}";
            if (MapSys.Instan == null) return "{\"ok\":false,\"error\":\"no-map\"}";
            MapSys.Instan.ClickSelectBtn(name);
            return "{\"ok\":true,\"name\":\"" + Json(name) + "\"}";
        }

        private static string NextDayJson(string path)
        {
            return DisabledJson("nextday-disabled-use-manual-ui");
            var modal = GetModal();
            if (!string.IsNullOrEmpty(modal.Kind) && !HasForce(path)) return BusyJson(modal);
            if (DataSys.Instan == null) return "{\"ok\":false,\"error\":\"no-game\"}";
            DataSys.Instan.TransTurnBtn();
            return "{\"ok\":true,\"nextDay\":true}";
        }

        private static string TalentInfoJson(string path)
        {
            string cell = "0/1";
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length == 2 && kv[0] == "cell") cell = Uri.UnescapeDataString(kv[1]);
                }
            }
            if (UiSys.Instan == null || UiSys.Instan.uiTrans == null || UiSys.Instan.uiTrans.Length <= 37)
                return "{\"ok\":false,\"error\":\"no-ui\"}";
            var panel = UiSys.Instan.uiTrans[37].Find("panel");
            var target = panel == null ? null : panel.Find("cells/" + cell);
            if (target == null) return "{\"ok\":false,\"error\":\"cell-not-found\",\"cell\":\"" + Json(cell) + "\"}";
            if (DauSys.Instan == null) return "{\"ok\":false,\"error\":\"no-dau\"}";
            DauSys.Instan.EnterTalentCell(target, true);
            var des = UiSys.Instan.uiTrans[37].Find("des");
            if (des == null) return "{\"ok\":false,\"error\":\"no-des\"}";
            var nameText = des.Find("name") == null ? null : des.Find("name").GetComponent<Text>();
            var desText = des.Find("des") == null ? null : des.Find("des").GetComponent<Text>();
            var levelText = des.Find("level") == null ? null : des.Find("level").GetComponent<Text>();
            return "{\"ok\":true,\"cell\":\"" + Json(cell) + "\",\"name\":\"" +
                   Json(nameText == null ? "" : nameText.text) + "\",\"des\":\"" +
                   Json(desText == null ? "" : desText.text) + "\",\"level\":\"" +
                   Json(levelText == null ? "" : levelText.text) + "\"}";
        }

        private static string UiBtnJson(string path)
        {
            int index = -1;
            string targetPath = null;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length != 2) continue;
                    if (kv[0] == "index") int.TryParse(kv[1], out index);
                    if (kv[0] == "path") targetPath = Uri.UnescapeDataString(kv[1]);
                }
            }
            if (index < 0 && string.IsNullOrEmpty(targetPath))
                return "{\"ok\":false,\"error\":\"missing-index-or-path\"}";
            var modal = GetModal();
            if (modal.Blocking && !HasForce(path) &&
                (string.IsNullOrEmpty(targetPath) || !IsInsideModal(targetPath, modal)))
                return BusyJson(modal);
            var uiButtons = UnityEngine.Object.FindObjectsOfType<UiBtn>();
            int current = 0;
            for (int i = 0; i < uiButtons.Length; i++)
            {
                var uiButton = uiButtons[i];
                if (uiButton == null || !uiButton.gameObject.activeInHierarchy) continue;
                string pathOf = PathOf(uiButton.transform);
                bool match = !string.IsNullOrEmpty(targetPath) ? pathOf == targetPath : current == index;
                if (!match)
                {
                    current++;
                    continue;
                }
                string type = uiButton.type.ToString();
                if (IsForbiddenAction(pathOf, null))
                    return DisabledJson("skip-action-disabled");
                uiButton.OnPointerClick(null);
                return "{\"ok\":true,\"type\":\"" + Json(type) + "\",\"path\":\"" + Json(pathOf) + "\"}";
            }
            return "{\"ok\":false,\"error\":\"uibutton-not-found\",\"index\":" + index +
                   ",\"path\":\"" + Json(targetPath) + "\"}";
        }

        private static string ClickJson(string path)
        {
            int index = -1;
            string targetPath = null;
            int q = path.IndexOf('?');
            if (q >= 0)
            {
                string[] parts = path.Substring(q + 1).Split('&');
                foreach (string part in parts)
                {
                    string[] kv = part.Split('=');
                    if (kv.Length != 2) continue;
                    if (kv[0] == "index") int.TryParse(kv[1], out index);
                    if (kv[0] == "path") targetPath = Uri.UnescapeDataString(kv[1]);
                }
            }
            if (index < 0 && string.IsNullOrEmpty(targetPath))
                return "{\"ok\":false,\"error\":\"missing-index-or-path\"}";
            var modal = GetModal();
            if (modal.Blocking && !HasForce(path) &&
                (string.IsNullOrEmpty(targetPath) || !IsInsideModal(targetPath, modal)))
                return BusyJson(modal);
            var buttons = UnityEngine.Object.FindObjectsOfType<Button>();
            int current = 0;
            for (int i = 0; i < buttons.Length; i++)
            {
                var button = buttons[i];
                if (button == null || !button.gameObject.activeInHierarchy) continue;
                string pathOf = PathOf(button.transform);
                bool match = !string.IsNullOrEmpty(targetPath) ? pathOf == targetPath : current == index;
                if (!match)
                {
                    if (string.IsNullOrEmpty(targetPath)) current++;
                    continue;
                }
                var label = button.GetComponentInChildren<Text>();
                string text = label == null ? "" : label.text;
                if (IsForbiddenAction(pathOf, text))
                    return DisabledJson("skip-action-disabled");
                button.onClick.Invoke();
                return "{\"ok\":true,\"clicked\":\"" + Json(text) + "\",\"path\":\"" + Json(pathOf) + "\"}";
            }
            // Some choice cards are UiBtn only.
            if (!string.IsNullOrEmpty(targetPath))
            {
                var uiButtons = UnityEngine.Object.FindObjectsOfType<UiBtn>();
                for (int i = 0; i < uiButtons.Length; i++)
                {
                    var uiButton = uiButtons[i];
                    if (uiButton == null || !uiButton.gameObject.activeInHierarchy) continue;
                    string pathOf = PathOf(uiButton.transform);
                    if (pathOf != targetPath) continue;
                    if (IsForbiddenAction(pathOf, null))
                        return DisabledJson("skip-action-disabled");
                    string type = uiButton.type.ToString();
                    uiButton.OnPointerClick(null);
                    return "{\"ok\":true,\"clicked\":\"\",\"type\":\"" + Json(type) +
                           "\",\"path\":\"" + Json(pathOf) + "\"}";
                }
            }
            return "{\"ok\":false,\"error\":\"button-not-found\",\"index\":" + index +
                   ",\"path\":\"" + Json(targetPath) + "\"}";
        }

        private static string PathOf(Transform transform)
        {
            var parts = new List<string>();
            var current = transform;
            while (current != null)
            {
                parts.Add(current.name);
                current = current.parent;
            }
            var sb = new StringBuilder();
            for (int i = parts.Count - 1; i >= 0; i--)
            {
                if (sb.Length > 0) sb.Append("/");
                sb.Append(parts[i]);
            }
            return sb.ToString();
        }

        private static object Field(object instance, string name)
        {
            if (instance == null) return null;
            var field = instance.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            return field == null ? null : field.GetValue(instance);
        }

        private static string IntArray(int[] values)
        {
            if (values == null) return "[]";
            var sb = new StringBuilder("[");
            for (int i = 0; i < values.Length; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append(values[i]);
            }
            return sb.Append("]").ToString();
        }

        private static string StringList(List<string> values)
        {
            if (values == null) return "[]";
            var sb = new StringBuilder("[");
            for (int i = 0; i < values.Count; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append("\"" + Json(values[i]) + "\"");
            }
            return sb.Append("]").ToString();
        }

        private static string Json(string value)
        {
            if (value == null) return "";
            var sb = new StringBuilder(value.Length + 8);
            foreach (char c in value)
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








