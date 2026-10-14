/*
 * Northwind AI chat widget - reusable in any app.
 * <script src="/static/chat-widget.js" data-endpoint="/chat" data-title="Ask AI" defer></script>
 * The endpoint must accept POST {question, session_id} and return {answer, sources, session_id}.
 */
(function () {
  const script = document.currentScript;
  const endpoint = (script && script.dataset.endpoint) || "/chat";
  const title = (script && script.dataset.title) || "Ask AI";
  const storageKey = "nw-chat-session";

  function getSession() { try { return sessionStorage.getItem(storageKey); } catch (e) { return null; } }
  function setSession(id) { try { if (id) sessionStorage.setItem(storageKey, id); } catch (e) { /* ignore */ } }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function formatAnswer(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(\d+)\]/g, '<sup class="nw-cite">[$1]</sup>')
      .replace(/\n/g, "<br>");
  }

  const button = document.createElement("button");
  button.type = "button";
  button.className = "nw-chat-button";
  button.setAttribute("aria-label", title);
  button.textContent = "💬";

  const panel = document.createElement("section");
  panel.className = "nw-chat-panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", title);
  panel.innerHTML = `
    <header class="nw-chat-header">
      <span>🤖 ${escapeHtml(title)}</span>
      <button type="button" class="nw-chat-close" aria-label="Close">×</button>
    </header>
    <div class="nw-chat-messages" role="log" aria-live="polite"></div>
    <form class="nw-chat-form">
      <input type="text" name="q" placeholder="Ask about policies, runbooks..." autocomplete="off" maxlength="2000">
      <button type="submit">Send</button>
    </form>
    <footer class="nw-chat-footer">Uses public &amp; internal pages only. Confidential pages are never shared with the assistant.</footer>`;

  document.body.append(button, panel);

  const messages = panel.querySelector(".nw-chat-messages");
  const form = panel.querySelector(".nw-chat-form");
  const input = form.querySelector("input");

  function addMessage(role, html) {
    const el = document.createElement("div");
    el.className = `nw-msg nw-msg-${role}`;
    el.innerHTML = html;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function renderSources(sources) {
    const seen = new Set();
    const items = [];
    for (const s of sources || []) {
      const key = s.url || s.source;
      if (seen.has(key)) continue;
      seen.add(key);
      const section = s.section ? " - " + s.section.split(" > ").pop() : "";
      const label = escapeHtml(`[${s.id}] ${s.title || s.source}${section}`);
      items.push(s.url ? `<li><a href="${escapeHtml(s.url)}">${label}</a></li>` : `<li>${label}</li>`);
    }
    return items.length ? `<div class="nw-sources"><span>Sources</span><ul>${items.join("")}</ul></div>` : "";
  }

  function toggle(open) {
    panel.hidden = !open;
    button.classList.toggle("nw-open", open);
    if (open) {
      if (!messages.children.length) {
        addMessage("bot", "Hi! Ask me anything about our policies, runbooks and processes.");
      }
      input.focus();
    }
  }

  button.addEventListener("click", () => toggle(panel.hidden));
  panel.querySelector(".nw-chat-close").addEventListener("click", () => toggle(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) toggle(false);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    input.value = "";
    input.disabled = true;
    addMessage("user", escapeHtml(question));
    const pending = addMessage("bot", '<span class="nw-typing">Searching the wiki…</span>');

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: getSession() }),
      });
      const data = await response.json();
      setSession(data.session_id);
      pending.innerHTML = formatAnswer(data.answer || "No answer.") + renderSources(data.sources);
    } catch (error) {
      pending.textContent = "Sorry, the assistant could not be reached.";
    } finally {
      input.disabled = false;
      input.focus();
      messages.scrollTop = messages.scrollHeight;
    }
  });
})();
