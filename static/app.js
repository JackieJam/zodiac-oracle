const signs = [
  ["aries", "白羊座", "Aries", "3.21 - 4.19"],
  ["taurus", "金牛座", "Taurus", "4.20 - 5.20"],
  ["gemini", "双子座", "Gemini", "5.21 - 6.21"],
  ["cancer", "巨蟹座", "Cancer", "6.22 - 7.22"],
  ["leo", "狮子座", "Leo", "7.23 - 8.22"],
  ["virgo", "处女座", "Virgo", "8.23 - 9.22"],
  ["libra", "天秤座", "Libra", "9.23 - 10.23"],
  ["scorpio", "天蝎座", "Scorpio", "10.24 - 11.21"],
  ["sagittarius", "射手座", "Sagittarius", "11.22 - 12.21"],
  ["capricorn", "摩羯座", "Capricorn", "12.22 - 1.19"],
  ["aquarius", "水瓶座", "Aquarius", "1.20 - 2.18"],
  ["pisces", "双鱼座", "Pisces", "2.19 - 3.20"],
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
      ([key, cn, en, range]) => `
      <button class="sign-card ${key === state.sign ? "active" : ""}" data-sign="${key}">
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
  await fetchReport(`/api/horoscope/public?sign=${encodeURIComponent(sign)}&period=${state.period}`);
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
  document.querySelector("#disclaimer").textContent = `${data.disclaimer} ${data.ephemeris_notice || ""}`;
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
    const response = await fetch("/api/horoscope/ask", {
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
