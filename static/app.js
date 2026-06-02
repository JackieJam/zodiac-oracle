const signs = [
  ["aries", "白羊座", "Aries", "3.21 - 4.19",
   '<svg viewBox="0 0 48 48"><circle cx="24" cy="30" r="10" /><path d="M14 30 C14 14 24 8 24 8 C24 8 34 14 34 30" /><path d="M10 16 Q4 8 8 2" /><path d="M38 16 Q44 8 40 2" /></svg>'],
  ["taurus", "金牛座", "Taurus", "4.20 - 5.20",
   '<svg viewBox="0 0 48 48"><path d="M10 14 Q4 4 14 8" /><path d="M38 14 Q44 4 34 8" /><circle cx="24" cy="28" r="12" /><circle cx="24" cy="28" r="4" /></svg>'],
  ["gemini", "双子座", "Gemini", "5.21 - 6.21",
   '<svg viewBox="0 0 48 48"><line x1="14" y1="10" x2="34" y2="10" /><line x1="14" y1="38" x2="34" y2="38" /><line x1="14" y1="10" x2="14" y2="38" /><line x1="34" y1="10" x2="34" y2="38" /><line x1="14" y1="18" x2="34" y2="30" /><line x1="14" y1="30" x2="34" y2="18" /></svg>'],
  ["cancer", "巨蟹座", "Cancer", "6.22 - 7.22",
   '<svg viewBox="0 0 48 48"><path d="M10 24 A10 10 0 0 1 30 24" /><circle cx="34" cy="28" r="8" /><circle cx="34" cy="28" r="3" /></svg>'],
  ["leo", "狮子座", "Leo", "7.23 - 8.22",
   '<svg viewBox="0 0 48 48"><path d="M16 28 A8 8 0 1 1 32 28 A8 8 0 1 1 16 28" /><path d="M24 20 A12 12 0 0 1 36 28" /><path d="M24 20 A12 12 0 0 0 12 28" /><circle cx="28" cy="24" r="2" /></svg>'],
  ["virgo", "处女座", "Virgo", "8.23 - 9.22",
   '<svg viewBox="0 0 48 48"><path d="M12 38 L12 16 Q12 8 20 8 Q28 8 28 16" /><path d="M22 38 L22 16 Q22 8 30 8 Q38 8 38 16" /><path d="M32 38 L38 38" /><path d="M32 26 A6 6 0 0 1 38 32" /></svg>'],
  ["libra", "天秤座", "Libra", "9.23 - 10.23",
   '<svg viewBox="0 0 48 48"><line x1="24" y1="38" x2="24" y2="22" /><line x1="10" y1="22" x2="38" y2="22" /><path d="M10 22 Q10 12 24 12 Q38 12 38 22" /><line x1="8" y1="38" x2="40" y2="38" /></svg>'],
  ["scorpio", "天蝎座", "Scorpio", "10.24 - 11.21",
   '<svg viewBox="0 0 48 48"><path d="M12 38 L12 16 Q12 8 20 8 Q28 8 28 16" /><path d="M22 38 L22 26" /><path d="M32 38 L32 20 Q32 14 38 14 Q44 14 44 20 L44 10" /></svg>'],
  ["sagittarius", "射手座", "Sagittarius", "11.22 - 12.21",
   '<svg viewBox="0 0 48 48"><line x1="10" y1="38" x2="38" y2="10" /><path d="M30 10 L38 10 L38 18" /><circle cx="24" cy="24" r="4" /></svg>'],
  ["capricorn", "摩羯座", "Capricorn", "12.22 - 1.19",
   '<svg viewBox="0 0 48 48"><path d="M12 36 L12 24 Q12 16 20 16 L28 16 Q36 16 36 24 L36 12" /><path d="M36 24 Q36 32 30 36 Q24 40 20 36 Q14 30 22 28" /></svg>'],
  ["aquarius", "水瓶座", "Aquarius", "1.20 - 2.18",
   '<svg viewBox="0 0 48 48"><path d="M8 20 Q14 14 24 20 Q34 26 40 20" /><path d="M8 28 Q14 22 24 28 Q34 34 40 28" /></svg>'],
  ["pisces", "双鱼座", "Pisces", "2.19 - 3.20",
   '<svg viewBox="0 0 48 48"><path d="M8 16 Q18 10 24 16 Q30 22 40 16" /><line x1="24" y1="10" x2="24" y2="38" /><path d="M8 32 Q18 26 24 32 Q30 38 40 32" /></svg>'],
];

const state = {
  sign: "aries",
  period: "daily",
  lastMode: "public",
};

const signGrid = document.querySelector("#signGrid");
const scoreGrid = document.querySelector("#scoreGrid");
const highlights = document.querySelector("#highlights");
const actions = document.querySelector("#actions");
const evidenceList = document.querySelector("#evidenceList");
const reportPanel = document.querySelector(".report-panel");
const askAnswer = document.querySelector("#askAnswer");
const quickQuestions = document.querySelector("#quickQuestions");
const loader = document.querySelector("#loader");
let currentReport = null;

document.querySelector("#todayLabel").textContent = new Date().toLocaleDateString("zh-CN", {
  year: "numeric",
  month: "long",
  day: "numeric",
  weekday: "long",
});

function init() {
  renderSigns();
  bindEvents();
  loadPublic("aries");
}

function renderSigns() {
  signGrid.innerHTML = signs
    .map(
      ([key, cn, en, range, icon]) => `
      <button class="sign-card ${key === state.sign ? "active" : ""}" data-sign="${key}">
        <span class="sign-icon">${icon}</span>
        <b>${cn}</b>
        <span>${en}</span>
        <small>${range}</small>
      </button>
    `,
    )
    .join("");
}

function bindEvents() {
  signGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sign]");
    if (!button) return;
    loadPublic(button.dataset.sign);
  });

  document.querySelectorAll(".period").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".period").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.period = button.dataset.period;
      refresh();
    });
  });

  document.querySelector("#refreshButton").addEventListener("click", refresh);

  document.querySelector("#askForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const textarea = event.currentTarget.elements.question;
    await askChart(textarea.value);
  });

  quickQuestions.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-question]");
    if (!button) return;
    document.querySelector("#askForm textarea").value = button.dataset.question;
    await askChart(button.dataset.question);
  });
}

async function refresh() {
  await loadPublic(state.sign);
}

async function loadPublic(sign) {
  state.sign = sign;
  state.lastMode = "public";
  renderSigns();
  await fetchReport(`/horoscope/api/horoscope/public?sign=${encodeURIComponent(sign)}&period=${state.period}`);
}

async function fetchReport(url, options = {}) {
  reportPanel.classList.add("is-loading");
  loader.classList.add("active");
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "请求失败");
    }
    const data = await response.json();
    renderReport(data);
  } catch (error) {
    document.querySelector("#reportTitle").textContent = "生成失败";
    document.querySelector("#reportSummary").textContent = error.message;
  } finally {
    reportPanel.classList.remove("is-loading");
    loader.classList.remove("active");
  }
}

function renderReport(data) {
  currentReport = data;
  document.querySelector("#reportMode").textContent = data.period.type === "daily" ? "今日星象" : "本周星象";
  document.querySelector("#reportTitle").textContent = `${data.subject} · ${data.period.type === "daily" ? "今日" : "本周"} ${data.overall_score}`;
  document.querySelector("#reportSummary").textContent = data.summary;
  document.querySelector("#disclaimer").textContent = data.disclaimer || "";
  askAnswer.textContent = "星象已经展开。你可以把今天最在意的问题写下来，让星盘给出一段更贴近你的解释。";

  const deep = data.deep_reading || {};
  document.querySelector("#deepHeadline").textContent = deep.headline || "等待星辰落位";
  document.querySelector("#deepWhy").textContent = deep.why_it_matters || "";
  document.querySelector("#deepBlindSpot").textContent = deep.blind_spot || "";
  document.querySelector("#deepBestMove").textContent = deep.best_move || "";
  document.querySelector("#deepRitual").textContent = deep.micro_ritual || "";
  renderQuickQuestions(data.suggested_questions || deep.reflection_questions || []);

  scoreGrid.innerHTML = Object.values(data.scores)
    .map(
      (item) => `
      <div class="score-card">
        <span>${item.label}</span>
        <strong>${item.score}</strong>
      </div>
    `,
    )
    .join("");

  highlights.innerHTML = data.highlights.map((item) => `<li>${item}</li>`).join("");
  actions.innerHTML = data.actions.map((item) => `<li>${item}</li>`).join("");
  evidenceList.innerHTML = data.evidence
    .map(
      (item) => `
      <div class="evidence-item">
        <strong>${item.planet} ${item.aspect_cn}</strong>
        <span>${item.description} 主题：${item.theme}</span>
        <span class="confidence">${Math.round(item.confidence * 100)}%</span>
      </div>
    `,
    )
    .join("");
}

function renderQuickQuestions(questions) {
  quickQuestions.innerHTML = questions
    .slice(0, 4)
    .map((question) => `<button type="button" data-question="${escapeAttribute(question)}">${escapeHTML(question)}</button>`)
    .join("");
}

async function askChart(question) {
  if (!currentReport) {
    askAnswer.textContent = "请先选择一个星座，让星盘展开。";
    return;
  }
  askAnswer.classList.add("thinking");
  askAnswer.textContent = "星盘正在回声室里重新排列今日相位...";
  try {
    const response = await fetch("/horoscope/api/horoscope/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report: currentReport, question }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "追问失败");
    }
    const data = await response.json();
    askAnswer.textContent = data.answer;
  } catch (error) {
    askAnswer.textContent = error.message;
  } finally {
    askAnswer.classList.remove("thinking");
  }
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHTML(value).replaceAll("`", "&#096;");
}

init();
