/**
 * ResearchAgent — Chat Interface Logic
 *
 * All visual "thinking" content per step is generated purely on the frontend.
 * No changes required to agent.py or api.py.
 *
 * BACKEND_URL:
 *   - Local dev  → http://localhost:5000  (automatic)
 *   - Production → set window.BACKEND_URL in a <script> tag, OR
 *                  update this string directly before deploying.
 */

const CONFIG = {
  // ⚙️  Change this string to your deployed API URL when going live.
  // e.g. "https://your-api.railway.app" or "https://your-api.onrender.com"
  BACKEND_URL: window.BACKEND_URL || "autonomous-research-agent-production-d61d.up.railway.app",
  GITHUB_URL:  "https://github.com/mr-ahtashamulhaq/autonomous-research-agent",
};

/* ── Pipeline step metadata ──────────────────────────────── */
const STEPS = [
  { id: "plan", label: "Planning search queries", icon: "◈" },
  { id: "search", label: "Searching the web", icon: "◎" },
  { id: "read", label: "Reading articles", icon: "◉" },
  { id: "synthesise", label: "Synthesising report", icon: "◆" },
  { id: "review", label: "Fact-checking & finalising", icon: "✓" },
];

/**
 * Engaging per-step detail content shown while each node is running.
 * These are displayed as animated "thinking" items - no backend changes needed.
 * Each item stagger-fades in 400ms apart to feel like real activity.
 */
const STEP_CONTENT = {
  plan: {
    headline: "Decomposing topic into 5 targeted research angles…",
    items: [
      { icon: "📰", text: "Recent news & developments" },
      { icon: "🎓", text: "Academic & expert analysis" },
      { icon: "📊", text: "Statistics & quantitative data" },
      { icon: "🏭", text: "Real-world applications & case studies" },
      { icon: "⚠️", text: "Challenges, risks & criticism" },
    ],
  },
  search: {
    headline: "Sending 5 queries to Tavily Search API (max 5 results each)…",
    items: [
      { icon: "⟳", text: "Query 1 → collecting top results…" },
      { icon: "⟳", text: "Query 2 → collecting top results…" },
      { icon: "⟳", text: "Query 3 → collecting top results…" },
      { icon: "⟳", text: "Query 4 → collecting top results…" },
      { icon: "⟳", text: "Query 5 → collecting top results…" },
    ],
  },
  read: {
    headline: "Calling Tavily Extract API on top 8 source URLs…",
    items: [
      { icon: "🔗", text: "Deduplicating & ranking 25 candidate URLs" },
      { icon: "📄", text: "Extracting full article text (not just snippets)" },
      { icon: "✂️", text: "Capturing up to 3,000 chars per source" },
      { icon: "📚", text: "Building ~24,000 char context window for LLM" },
      { icon: "🧹", text: "Stripping ads, nav & boilerplate HTML" },
    ],
  },
  synthesise: {
    headline: "llama-3.3-70b writing your structured report…",
    items: [
      { icon: "✍️", text: "## Executive Summary (2–3 key sentences)" },
      { icon: "✍️", text: "## Key Findings (4–6 insights with subheadings)" },
      { icon: "✍️", text: "## Analysis & Implications (trends & patterns)" },
      { icon: "✍️", text: "## Conclusion (forward-looking synthesis)" },
      { icon: "🔗", text: "Adding inline [Source: domain.com] citations" },
    ],
  },
  review: {
    headline: "Second LLM pass: fact-checking every claim vs sources…",
    items: [
      { icon: "🔍", text: "Verifying each claim is supported by a source" },
      { icon: "🚫", text: "Removing or softening unsupported statements" },
      { icon: "🔢", text: "Upgrading citations to [1][2] numbered format" },
      { icon: "📋", text: "Building formatted ## Sources reference list" },
      { icon: "📊", text: "Adding ## Research Confidence assessment" },
    ],
  },
};

/* ── DOM refs ──────────────────────────────────────────────── */
const welcomeScreen = document.getElementById("welcome-screen");
const chatMessages = document.getElementById("chat-messages");
const topicInput = document.getElementById("topic-input");
const researchBtn = document.getElementById("research-btn");
const inputChips = document.getElementById("input-chips");

/* ── State ─────────────────────────────────────────────────── */
let currentReport = "";
let progressBubbleEl = null;
let isRunning = false;

/* ── marked.js config ─────────────────────────────────────── */
marked.setOptions({ breaks: true, gfm: true, headerIds: false });

/* ── Auto-grow textarea ───────────────────────────────────── */
topicInput.addEventListener("input", () => {
  topicInput.style.height = "auto";
  topicInput.style.height = Math.min(topicInput.scrollHeight, 160) + "px";
});

/* ── Chip clicks ──────────────────────────────────────────── */
inputChips.querySelectorAll(".chip").forEach(chip => {
  chip.addEventListener("click", () => {
    topicInput.value = chip.dataset.topic;
    topicInput.focus();
    topicInput.dispatchEvent(new Event("input"));
  });
});

/* ── Enter to submit (Shift+Enter = newline) ──────────────── */
topicInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
});

researchBtn.addEventListener("click", handleSubmit);

/* ── Welcome → chat transition ───────────────────────────── */
function showChatMode() {
  welcomeScreen.classList.add("hidden");
  chatMessages.classList.remove("hidden");
}

/* ── Append a message bubble ──────────────────────────────── */
function appendMessage(role, contentEl) {
  const msg = document.createElement("div");
  msg.className = `message message-${role}`;

  const avatar = document.createElement("div");
  avatar.className = `avatar avatar-${role}`;

  if (role === "user") {
    // User: letter initial
    avatar.textContent = "U";
  } else {
    // Agent: coral triangle
    avatar.innerHTML = `<svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <polygon points="10,2 19,18 1,18" fill="#cc785c"/>
    </svg>`;
  }

  const bubbleWrap = document.createElement("div");
  bubbleWrap.className = "bubble";

  if (role === "user") {
    bubbleWrap.textContent = contentEl;
  } else {
    bubbleWrap.appendChild(contentEl);
  }

  msg.appendChild(avatar);
  msg.appendChild(bubbleWrap);
  chatMessages.appendChild(msg);
  scrollToBottom();
  return msg;
}

/* ── Build progress bubble with engaging step details ─────── */
function createProgressBubble() {
  const wrapper = document.createElement("div");
  wrapper.className = "progress-bubble";

  wrapper.innerHTML = `
    <div class="progress-header">
      <span class="progress-title">Agent Pipeline</span>
      <span class="progress-pct" id="prog-pct">0%</span>
    </div>
    <div class="progress-bar-track">
      <div class="progress-bar-fill" id="prog-bar"></div>
    </div>
    <div class="progress-steps" id="prog-steps"></div>
  `;

  const stepsEl = wrapper.querySelector("#prog-steps");
  STEPS.forEach(s => {
    const el = document.createElement("div");
    el.className = "p-step";
    el.id = `ps-${s.id}`;

    // Build the step detail items HTML
    const detailContent = STEP_CONTENT[s.id];
    const itemsHtml = detailContent.items.map((item, i) => `
      <div class="p-detail-item" data-index="${i}">
        <span class="p-detail-item-icon">${item.icon}</span>
        <span>${item.text}</span>
        <span class="p-detail-item-dot"></span>
      </div>
    `).join("");

    el.innerHTML = `
      <div class="p-step-dot">${s.icon}</div>
      <div style="flex:1;min-width:0;">
        <span class="p-step-label">${s.label}</span>
        <div class="p-step-detail" id="psd-${s.id}">
          <div class="p-detail-headline">
            ${detailContent.headline}<span class="cursor-blink"></span>
          </div>
          ${itemsHtml}
        </div>
      </div>
    `;
    stepsEl.appendChild(el);
  });

  return wrapper;
}

/* ── Animate step detail items appearing one by one ──────── */
function animateStepDetail(nodeId) {
  const detail = progressBubbleEl?.querySelector(`#psd-${nodeId}`);
  if (!detail) return;

  const items = detail.querySelectorAll(".p-detail-item");
  items.forEach((item, i) => {
    // Stagger each item: 350ms apart
    setTimeout(() => {
      item.classList.add("visible");
      scrollToBottom();
    }, i * 380);
  });
}

/* ── Update progress bubble state ─────────────────────────── */
function setProgress(pct, nodeId) {
  if (!progressBubbleEl) return;

  const bar = progressBubbleEl.querySelector("#prog-bar");
  const pctEl = progressBubbleEl.querySelector("#prog-pct");
  if (bar) bar.style.width = `${pct}%`;
  if (pctEl) pctEl.textContent = `${pct}%`;

  const idx = STEPS.findIndex(s => s.id === nodeId);

  // Mark all previous steps done
  for (let i = 0; i < idx; i++) {
    const prevEl = progressBubbleEl.querySelector(`#ps-${STEPS[i].id}`);
    if (prevEl && !prevEl.classList.contains("done")) {
      prevEl.classList.remove("active");
      prevEl.classList.add("done");
      prevEl.querySelector(".p-step-dot").textContent = "✓";
    }
  }

  // Activate current step
  const curEl = progressBubbleEl.querySelector(`#ps-${nodeId}`);
  if (curEl && !curEl.classList.contains("active")) {
    curEl.classList.add("active");
    const icon = STEPS[idx]?.icon ?? "◈";
    curEl.querySelector(".p-step-dot").textContent = icon;

    // Trigger the animated detail items
    animateStepDetail(nodeId);
  }
}

/* ── Mark all steps done at 100% ─────────────────────────── */
function finishProgress() {
  if (!progressBubbleEl) return;
  const bar = progressBubbleEl.querySelector("#prog-bar");
  const pct = progressBubbleEl.querySelector("#prog-pct");
  if (bar) bar.style.width = "100%";
  if (pct) pct.textContent = "100%";

  STEPS.forEach(s => {
    const el = progressBubbleEl.querySelector(`#ps-${s.id}`);
    if (el) {
      el.classList.remove("active");
      el.classList.add("done");
      el.querySelector(".p-step-dot").textContent = "✓";
    }
  });
}

/* ── Render the final report bubble ───────────────────────── */
function renderReport(topic, markdown) {
  currentReport = markdown;

  const wrapper = document.createElement("div");
  wrapper.className = "report-bubble";

  const header = document.createElement("div");
  header.className = "report-bubble-header";
  header.innerHTML = `
    <span class="report-bubble-label">Research Report</span>
    <button class="copy-btn" id="copy-btn" title="Copy report">
      <span id="copy-icon">📋</span>
      <span id="copy-label">Copy</span>
    </button>
  `;

  const body = document.createElement("div");
  body.className = "report-bubble-body";

  const md = document.createElement("div");
  md.className = "report-md";
  md.innerHTML = marked
    .parse(markdown)
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");

  body.appendChild(md);
  wrapper.appendChild(header);
  wrapper.appendChild(body);

  // Copy button
  header.querySelector("#copy-btn").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(currentReport);
      header.querySelector("#copy-icon").textContent = "✓";
      header.querySelector("#copy-label").textContent = "Copied!";
      setTimeout(() => {
        header.querySelector("#copy-icon").textContent = "📋";
        header.querySelector("#copy-label").textContent = "Copy";
      }, 2000);
    } catch { /* ignore */ }
  });

  appendMessage("agent", wrapper);
  scrollToBottom();
}

/* ── Error bubble ─────────────────────────────────────────── */
function renderError(message) {
  const el = document.createElement("div");
  el.className = "error-bubble";
  el.textContent = `⚠️  ${message}`;
  appendMessage("agent", el);
}

/* ── Toggle loading state ─────────────────────────────────── */
function setLoading(loading) {
  isRunning = loading;
  researchBtn.disabled = loading;
  topicInput.disabled = loading;
  researchBtn.classList.toggle("loading", loading);
}

/* ── Scroll chat to bottom ────────────────────────────────── */
function scrollToBottom() {
  const main = document.getElementById("chat-main");
  if (main) main.scrollTo({ top: main.scrollHeight, behavior: "smooth" });
}

/* ── Main submit handler ──────────────────────────────────── */
async function handleSubmit() {
  if (isRunning) return;

  const topic = topicInput.value.trim();
  if (!topic) { topicInput.focus(); return; }

  showChatMode();
  appendMessage("user", topic);

  topicInput.value = "";
  topicInput.style.height = "auto";

  // Build and show progress bubble
  const progressEl = createProgressBubble();
  progressBubbleEl = progressEl;
  appendMessage("agent", progressEl);

  setLoading(true);

  try {
    /**
     * FastAPI returns text/event-stream.
     * We use fetch + ReadableStream (not EventSource) because
     * EventSource only supports GET - our endpoint is POST.
     */
    const response = await fetch(`${CONFIG.BACKEND_URL}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });

    if (!response.ok) {
      throw new Error(`Server error ${response.status}: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalReport = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop(); // keep incomplete chunk

      for (const rawEvent of events) {
        if (!rawEvent.trim()) continue;

        let type = "message", dataStr = "";
        for (const line of rawEvent.split("\n")) {
          if (line.startsWith("event:")) type = line.slice(6).trim();
          if (line.startsWith("data:")) dataStr = line.slice(5).trim();
        }
        if (!dataStr) continue;

        let payload;
        try { payload = JSON.parse(dataStr); } catch { continue; }

        if (type === "progress") {
          setProgress(payload.percent, payload.node);
        } else if (type === "done") {
          finalReport = payload.report;
          finishProgress();
        } else if (type === "error") {
          throw new Error(payload.message);
        }
      }
    }

    if (finalReport) renderReport(topic, finalReport);

  } catch (err) {
    console.error("[ResearchAgent]", err);
    renderError(
      err.message ||
      "Could not connect to backend. Is the API server running on port 5000?"
    );
  } finally {
    setLoading(false);
    progressBubbleEl = null;
  }
}
