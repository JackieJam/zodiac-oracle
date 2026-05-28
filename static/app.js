const signs = [
  ["aries", "白羊座", "Aries"],
  ["taurus", "金牛座", "Taurus"],
  ["gemini", "双子座", "Gemini"],
  ["cancer", "巨蟹座", "Cancer"],
  ["leo", "狮子座", "Leo"],
  ["virgo", "处女座", "Virgo"],
  ["libra", "天秤座", "Libra"],
  ["scorpio", "天蝎座", "Scorpio"],
  ["sagittarius", "射手座", "Sagittarius"],
  ["capricorn", "摩羯座", "Capricorn"],
  ["aquarius", "水瓶座", "Aquarius"],
  ["pisces", "双鱼座", "Pisces"],
];

const state = {
  sign: "aries",
  period: "daily",
  lastMode: "public",
  lastPersonalPayload: null,
};

const signGrid = document.querySelector("#signGrid");
const scoreGrid = document.querySelector("#scoreGrid");
const highlights = document.querySelector("#highlights");
const actions = document.querySelector("#actions");
const evidenceList = document.querySelector("#evidenceList");
const reportPanel = document.querySelector(".report-panel");
const askAnswer = document.querySelector("#askAnswer");
const askSource = document.querySelector("#askSource");
const quickQuestions = document.querySelector("#quickQuestions");
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
      ([key, cn, en]) => `
      <button class="sign-card ${key === state.sign ? "active" : ""}" data-sign="${key}">
        <b>${cn}</b>
        <span>${en}</span>
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

  document.querySelector("#personalForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = {
      name: formData.get("name") || null,
      birth_date: formData.get("birth_date"),
      birth_time: formData.get("birth_time") || null,
      timezone: formData.get("timezone"),
      latitude: Number(formData.get("latitude")),
      longitude: Number(formData.get("longitude")),
      period: state.period,
    };
    state.lastPersonalPayload = payload;
    state.lastMode = "personal";
    await fetchReport("/api/horoscope/personal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  });

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
  if (state.lastMode === "personal" && state.lastPersonalPayload) {
    await fetchReport("/api/horoscope/personal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...state.lastPersonalPayload, period: state.period }),
    });
    return;
  }
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
  }
}

function renderReport(data) {
  currentReport = data;
  document.querySelector("#reportMode").textContent = data.mode === "personal" ? "个人化行运" : "大众运势";
  document.querySelector("#reportTitle").textContent = `${data.subject} · ${data.period.type === "daily" ? "今日" : "本周"} ${data.overall_score}`;
  document.querySelector("#reportSummary").textContent = data.summary;
  document.querySelector("#disclaimer").textContent = `${data.disclaimer} ${data.ephemeris_notice || ""}`;
  askSource.textContent = data.writer === "rules+llm" ? "LLM 润色摘要" : "规则摘要";
  askAnswer.textContent = "你可以围绕事业、感情、财富、身心或某条相位继续追问。";

  const deep = data.deep_reading || {};
  document.querySelector("#deepHeadline").textContent = deep.headline || "等待星历信号";
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
    askAnswer.textContent = "请先生成一份星历报告。";
    return;
  }
  askAnswer.textContent = "正在根据当前星历整理回答...";
  askSource.textContent = "生成中";
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
    askSource.textContent = data.source === "rules+llm" ? "星历 + LLM" : "星历规则";
  } catch (error) {
    askAnswer.textContent = error.message;
    askSource.textContent = "失败";
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
