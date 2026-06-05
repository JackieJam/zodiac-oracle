const { askHoroscope, getPublicHoroscope } = require("../../utils/api");
const { findSign } = require("../../utils/signs");

const LOADING_STAGES = [
  "连接星历服务",
  "校准太阳星座",
  "读取行运相位",
  "整理四维评分",
  "生成星象解读"
];

function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

Page({
  data: {
    actions: [],
    answer: "",
    deepReading: {},
    disclaimer: "",
    error: "",
    evidence: [],
    highlights: [],
    loading: true,
    loadingProgress: 6,
    loadingStage: LOADING_STAGES[0],
    period: "daily",
    question: "",
    quickQuestions: [],
    report: null,
    scores: [],
    sign: {},
    signKey: "aries",
    submitting: false,
    summary: "",
    title: ""
  },

  onLoad(options) {
    const signKey = options.sign || "aries";
    const period = options.period || "daily";
    const sign = findSign(signKey);
    this.setData({ period, sign, signKey });
    wx.setNavigationBarTitle({ title: `${sign.cn}运势` });
    this.loadReport();
  },

  onUnload() {
    this.stopLoadingProgress();
  },

  startLoadingProgress() {
    this.stopLoadingProgress();
    this.setData({
      loadingProgress: 6,
      loadingStage: LOADING_STAGES[0]
    });

    this.loadingTimer = setInterval(() => {
      const current = this.data.loadingProgress;
      if (current >= 94) {
        return;
      }

      const step = current < 42 ? 7 : current < 76 ? 4 : 2;
      const next = Math.min(94, current + step);
      const stageIndex = Math.min(
        LOADING_STAGES.length - 1,
        Math.floor((next / 100) * LOADING_STAGES.length)
      );

      this.setData({
        loadingProgress: next,
        loadingStage: LOADING_STAGES[stageIndex]
      });
    }, 520);
  },

  stopLoadingProgress() {
    if (this.loadingTimer) {
      clearInterval(this.loadingTimer);
      this.loadingTimer = null;
    }
  },

  finishLoadingProgress() {
    this.stopLoadingProgress();
    this.setData({
      loadingProgress: 100,
      loadingStage: "星象已就位"
    });
  },

  async loadReport() {
    this.setData({ error: "", loading: true });
    this.startLoadingProgress();
    try {
      const report = await getPublicHoroscope(this.data.signKey, this.data.period);
      getApp().globalData.lastReport = report;
      this.renderReport(report);
      this.finishLoadingProgress();
      await wait(260);
    } catch (error) {
      this.stopLoadingProgress();
      const message = error.message || "报告生成失败";
      this.setData({
        error: message.includes("timeout") ? "远端星历服务响应超时，请稍后重试。" : message
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  renderReport(report) {
    const deepReading = report.deep_reading || {};
    const scores = Object.keys(report.scores || {}).map((key) => ({
      key,
      ...report.scores[key]
    }));
    const quickQuestions = (report.suggested_questions || deepReading.reflection_questions || []).slice(0, 4);
    this.setData({
      actions: report.actions || [],
      answer: "星象已经展开。你可以写下今天最在意的问题，让星盘给出一段更贴近你的解释。",
      deepReading,
      disclaimer: report.disclaimer || "",
      evidence: report.evidence || [],
      highlights: report.highlights || [],
      quickQuestions,
      report,
      scores,
      summary: report.summary || "",
      title: `${report.subject || this.data.sign.cn} · ${report.period.type === "daily" ? "今日" : "本周"} ${report.overall_score || ""}`
    });
  },

  onQuestionInput(event) {
    this.setData({ question: event.detail.value });
  },

  useQuickQuestion(event) {
    this.setData({ question: event.currentTarget.dataset.question });
  },

  async submitQuestion() {
    const question = this.data.question.trim();
    if (!question) {
      this.setData({ answer: "先写下一个具体问题，比如事业、关系、财富或身心状态。" });
      return;
    }
    if (question.length < 2) {
      this.setData({ answer: "问题再具体一点点会更好，比如“关系”或“事业压力”。" });
      return;
    }
    if (!this.data.report) {
      this.setData({ answer: "请先等待星象报告生成完成。" });
      return;
    }
    this.setData({ submitting: true, answer: "星象正在重新排列今日相位..." });
    try {
      const result = await askHoroscope(this.data.report, question);
      this.setData({ answer: result.answer || "暂时没有得到明确回应。" });
    } catch (error) {
      this.setData({ answer: error.message || "追问失败" });
    } finally {
      this.setData({ submitting: false });
    }
  }
});
