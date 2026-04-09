/* ── AI Advisor Tab ── */

var _aiConversationId = null;
var _aiStreaming = false;
var _aiLoaded = false;

var AI_QUICK_PROMPTS = {
  portfolio:
    "Analyze my portfolio through Ray Dalio's All Weather lens. Am I truly " +
    "diversified across economic environments (growth, recession, inflation, " +
    "deflation), or am I just diversified across ticker symbols? Compare me " +
    "to the All Weather template and share your opinion on what I might adjust.",
  outlook:
    "What's the macro environment telling us right now? Check sentiment, VIX, " +
    "yield curve, and any relevant FRED data. Then share your opinion using " +
    "Howard Marks' cycle framework on where we might be in the market cycle " +
    "and what positioning ideas are worth considering.",
  risk:
    "Channel Warren Buffett's thinking: look at my top holdings and sector " +
    "exposure and tell me: do I seem to understand what I own? Where's my " +
    "biggest concentration risk, and what's my margin of safety if markets " +
    "dropped 30%? Be honest with your opinion.",
  rebalance:
    "Give me a specific rebalance plan. Compare my current allocation to my " +
    "targets, calculate the exact dollar trades, and share your thoughts on " +
    "which trades to prioritize based on tax efficiency and market conditions.",
  tlh:
    "Check my portfolio for tax-loss harvesting opportunities. What's sitting " +
    "at a loss that I could consider selling, what are the substitute ETFs to " +
    "avoid wash sales, and roughly how much could I potentially save on taxes?",
  history:
    "Look at my portfolio history and trend over the recent period. How has " +
    "my portfolio performed? What was the peak, the worst drawdown, and the " +
    "overall growth rate? Share your thoughts on whether the trajectory looks healthy."
};

/* ── Initialization ── */

function aiInit() {
  if (_aiLoaded) return;
  _aiLoaded = true;
  _aiLoadConversations();
  _aiAutoResize();
}

function _aiAutoResize() {
  var input = document.getElementById("ai-chat-input");
  if (!input) return;
  input.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });
}

/* ── Quick Actions ── */

function aiSendQuick(key) {
  var prompt = AI_QUICK_PROMPTS[key];
  if (prompt) {
    var input = document.getElementById("ai-chat-input");
    if (input) input.value = prompt;
    aiSend();
  }
}

/* ── Send Message ── */

function aiSend() {
  if (_aiStreaming) return;
  var input = document.getElementById("ai-chat-input");
  if (!input) return;
  var text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.style.height = "auto";

  _aiHideWelcome();
  _aiAppendMessage("user", text);
  _aiStream(text);
}

function _aiStream(message) {
  _aiStreaming = true;
  _aiSetSending(true);

  var msgEl = _aiAppendMessage("assistant", "");
  var dots = document.createElement("span");
  dots.innerHTML =
    '<span class="ai-typing"></span>' +
    '<span class="ai-typing"></span>' +
    '<span class="ai-typing"></span>';
  msgEl.appendChild(dots);

  var body = JSON.stringify({
    message: message,
    conversation_id: _aiConversationId,
  });

  fetch("/api/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body,
  })
    .then(function (response) {
      if (response.status === 403) throw new Error("pro");
      if (response.status === 503) throw new Error("nokey");
      if (!response.ok) throw new Error("fail");

      var convId = response.headers.get("X-Conversation-Id");
      if (convId) _aiConversationId = parseInt(convId, 10);

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var fullText = "";
      var dotsRemoved = false;

      function read() {
        reader.read().then(function (result) {
          if (result.done) {
            _aiFinishStream(msgEl, fullText);
            return;
          }

          buffer += decoder.decode(result.value, { stream: true });
          var lines = buffer.split("\n");
          buffer = lines.pop();

          for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line.startsWith("data: ")) continue;
            var payload = line.substring(6);

            if (payload === "[DONE]") {
              _aiFinishStream(msgEl, fullText);
              return;
            }

            try {
              var data = JSON.parse(payload);
              if (data.error) {
                msgEl.innerHTML = '<span style="color:var(--danger);">' +
                  _aiEsc(data.error) + "</span>";
                _aiFinishStream(msgEl, "");
                return;
              }
              if (data.token) {
                if (!dotsRemoved) {
                  dots.remove();
                  dotsRemoved = true;
                }
                fullText += data.token;
                msgEl.innerHTML = _aiFormatMarkdown(fullText);
                _aiScrollBottom();
              }
            } catch (e) {}
          }

          read();
        });
      }

      read();
    })
    .catch(function (e) {
      var errorMsg = "Something went wrong. Please try again.";
      if (e.message === "pro")
        errorMsg = "AI Advisor requires a Pro subscription.";
      else if (e.message === "nokey")
        errorMsg = "AI is not yet configured on the server.";

      msgEl.innerHTML = '<span style="color:var(--danger);">' +
        _aiEsc(errorMsg) + "</span>";
      _aiFinishStream(msgEl, "");
    });
}

function _aiFinishStream(msgEl, fullText) {
  _aiStreaming = false;
  _aiSetSending(false);
  if (fullText) {
    msgEl.innerHTML = _aiFormatMarkdown(fullText);
  }
  _aiScrollBottom();
  _aiLoadConversations();
}

/* ── Message Rendering ── */

function _aiAppendMessage(role, content) {
  var container = document.getElementById("ai-chat-messages");
  if (!container) return document.createElement("div");

  var el = document.createElement("div");
  el.className = "ai-msg ai-msg-" + role;
  if (content) {
    el.innerHTML = role === "user" ? _aiEsc(content) : _aiFormatMarkdown(content);
  }
  container.appendChild(el);
  _aiScrollBottom();
  return el;
}

function _aiHideWelcome() {
  var w = document.getElementById("ai-welcome");
  if (w) w.style.display = "none";
}

function _aiShowWelcome() {
  var w = document.getElementById("ai-welcome");
  if (w) w.style.display = "";
}

function _aiScrollBottom() {
  var container = document.getElementById("ai-chat-messages");
  if (container) {
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }
}

function _aiSetSending(sending) {
  var btn = document.getElementById("ai-send-btn");
  var input = document.getElementById("ai-chat-input");
  if (btn) {
    btn.disabled = sending;
    btn.textContent = sending ? "..." : "Send";
  }
  if (input) input.disabled = sending;
}

/* ── Markdown Formatting ── */

function _aiFormatMarkdown(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.*?)`/g, "<code>$1</code>")
    .replace(/\n\n/g, "<br><br>")
    .replace(/\n/g, "<br>");
}

function _aiEsc(s) {
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ── Conversation Management ── */

function _aiLoadConversations() {
  fetch("/api/ai/conversations")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var select = document.getElementById("ai-history-select");
      if (!select) return;
      var convs = d.conversations || [];
      var html = '<option value="">History (' + convs.length + ")</option>";
      convs.forEach(function (c) {
        var title = c.title || "Untitled";
        if (title.length > 40) title = title.substring(0, 40) + "...";
        var selected = c.id === _aiConversationId ? " selected" : "";
        html += '<option value="' + c.id + '"' + selected + ">" +
          _aiEsc(title) + "</option>";
      });
      select.innerHTML = html;
    })
    .catch(function () {});
}

function aiLoadConversation(id) {
  if (!id) return;
  id = parseInt(id, 10);

  fetch("/api/ai/conversations/" + id)
    .then(function (r) { return r.json(); })
    .then(function (d) {
      _aiConversationId = d.id;
      var container = document.getElementById("ai-chat-messages");
      if (!container) return;

      container.innerHTML = "";
      _aiHideWelcome();

      var msgs = d.messages || [];
      if (msgs.length === 0) {
        _aiShowWelcome();
        return;
      }
      msgs.forEach(function (m) {
        _aiAppendMessage(m.role, m.content);
      });
      _aiScrollBottom();
    })
    .catch(function () {});
}

function aiNewChat() {
  _aiConversationId = null;
  var container = document.getElementById("ai-chat-messages");
  if (container) container.innerHTML = "";
  _aiShowWelcome();

  var select = document.getElementById("ai-history-select");
  if (select) select.value = "";
}

/* ── Tab activation hook ── */

(function () {
  var origShowTab = window.showTab;
  if (typeof origShowTab === "function") {
    window.showTab = function (tab) {
      origShowTab(tab);
      if (tab === "ai") aiInit();
    };
  }

  if (window.ACTIVE_TAB === "ai") {
    setTimeout(aiInit, 0);
  }
})();
