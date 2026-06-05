# 观星日课Lite小程序前端

这是 `观星日课Lite` 的原生微信小程序前端。当前版本保留 FastAPI 后端，前端使用小程序页面调用现有接口。

## 本地运行

当前小程序默认调用远端 Ubuntu 服务器上的后端：

```text
https://jackieai.top/horoscope
```

后端接口示例：

```text
https://jackieai.top/horoscope/api/health
https://jackieai.top/horoscope/api/horoscope/public?sign=aries&period=daily
```

用微信开发者工具导入：

```text
/Users/jackie_m/Documents/Code_Projects/40_xingzuo/miniprogram
```

首次导入时可以把 `project.config.json` 里的 `appid` 从 `touristappid` 改成你的小程序 AppID，或在开发者工具里选择自己的 AppID。

## 本地 API 地址

小程序请求地址在这里配置：

```text
miniprogram/utils/config.js
```

默认值：

```js
apiBaseUrl: "https://jackieai.top/horoscope"
```

如果临时要改回本机后端，可把它改成 `http://127.0.0.1:8512`，并先在项目根目录运行 `uv run app.py`。

## 上线前

- 在微信公众平台配置“开发管理 > 开发设置 > 服务器域名 > request 合法域名”：`https://jackieai.top`。
- 如果开发者工具仍提示 `request:fail url not in domain list`，到“详情 > 域名信息”刷新项目配置后重新编译；只点“编译”不会强制拉取后台最新域名列表。
- 当前 `assets/app-icon*.png` 仅作为本地图标素材保留，`README.md` 和 `project.private.config.json` 也只用于本地开发；这些文件已在 `project.config.json` 的 `packOptions.ignore` 中排除，避免上传源码包超过 2MB 或触发无关代码质量提示。
- 确认后端 CORS、反向代理、日志和错误返回都适合线上环境。
- 如果详情页加载时微信开发者工具出现 `WAServiceMainContext Error: timeout`，优先部署最新后端：公开报告接口已改为规则快速返回并加缓存，避免等待 LLM 润色。
- 补齐小程序隐私协议、免责声明、分享文案和审核材料。
- 商业发布前再确认 Swiss Ephemeris / `pyswisseph` 授权边界。
