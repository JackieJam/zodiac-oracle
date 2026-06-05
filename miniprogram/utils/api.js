const { apiBaseUrl } = require("./config");

const RETRYABLE_ERRORS = ["ERR_CONNECTION_CLOSED", "timeout", "abort", "fail"];
const REQUEST_DEADLINE_MS = 55000;
const WX_REQUEST_TIMEOUT_MS = 300000;

function buildUrl(path, query) {
  const base = apiBaseUrl.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const params = query
    ? Object.keys(query)
        .filter((key) => query[key] !== undefined && query[key] !== null && query[key] !== "")
        .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(query[key])}`)
        .join("&")
    : "";
  return `${base}${normalizedPath}${params ? `?${params}` : ""}`;
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function shouldRetry(message, statusCode) {
  if ([502, 503, 504].includes(statusCode)) {
    return true;
  }
  return RETRYABLE_ERRORS.some((item) => message.includes(item));
}

function request(path, options = {}) {
  const maxRetries = options.retries ?? 1;
  const timeout = Math.min(options.timeout || REQUEST_DEADLINE_MS, REQUEST_DEADLINE_MS);

  function send(attempt) {
    const url = buildUrl(path, options.query);

    return new Promise((resolve, reject) => {
      let settled = false;

      function finish(handler, value) {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(deadlineTimer);
        handler(value);
      }

      const deadlineTimer = setTimeout(() => {
        finish(reject, new Error(`请求远端后端超时：${url}`));
      }, timeout);

      wx.request({
        url,
        method: options.method || "GET",
        data: options.data,
        timeout: WX_REQUEST_TIMEOUT_MS,
        header: {
          "Content-Type": "application/json",
          ...(options.header || {})
        },
        success(res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            finish(resolve, res.data);
            return;
          }
          const detail = res.data && (res.data.detail || res.data.message);
          const message = detail || `请求失败：${res.statusCode}`;
          if (attempt < maxRetries && shouldRetry(message, res.statusCode)) {
            finish(resolve, sleep(600 * (attempt + 1)).then(() => send(attempt + 1)));
            return;
          }
          finish(reject, new Error(message));
        },
        fail(error) {
          const message = error.errMsg || "网络请求失败";
          if (settled) {
            return;
          }
          if (attempt < maxRetries && shouldRetry(message)) {
            finish(resolve, sleep(600 * (attempt + 1)).then(() => send(attempt + 1)));
            return;
          }
          finish(reject, new Error(message.includes("timeout") ? `请求远端后端超时：${url}` : message));
        }
      });
    });
  }

  return send(0);
}

function getPublicHoroscope(sign, period) {
  return request("/api/horoscope/public", {
    query: { sign, period }
  });
}

function askHoroscope(report, question) {
  return request("/api/horoscope/ask", {
    method: "POST",
    data: { report, question },
    retries: 0
  });
}

module.exports = {
  askHoroscope,
  getPublicHoroscope
};
