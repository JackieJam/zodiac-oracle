# 星盘日课

一个“西洋热带占星”的专业星座评测 Web 工具原型。用户可以按出生日期快速找到 12 星座，查看今日/本周运势，并围绕真实星历报告继续追问。

## 功能

- 大众入口：`GET /api/horoscope/public?sign=aries&period=daily`
- 个人化入口：`POST /api/horoscope/personal`，后端保留，首屏暂不展示；后续可作为高级个人盘重做
- 星谕入口：`POST /api/horoscope/ask`，基于当前星象报告回答用户问题
- 统一输出：总评、事业/关系/财富/身心评分、星象启示、星辰提醒、今日指引、行运相位、免责声明
- 内容生成：默认使用规则模板；配置 `DEEPSEEK_API_KEY` 后会在不新增占星结论的前提下润色摘要，并为“星谕回声”提供更自然的互动回答
- 计算层：使用 Swiss Ephemeris / pyswisseph 计算真实行星黄经，并按主相位生成依据

## 运行

```bash
uv run app.py
```

打开：

```text
http://127.0.0.1:8000
```

当前脚本实际监听 `http://127.0.0.1:8512`；如果需要 8000 端口，可改 `app.py` 末尾的 `uvicorn.run` 参数或用独立 uvicorn 命令启动。

## 小程序前端

项目内已加入微信小程序前端骨架：

```text
miniprogram/
```

本地开发流程：

1. 用微信开发者工具导入 `/Users/jackie_m/Documents/Code_Projects/40_xingzuo/miniprogram`
2. 首次导入时把 `project.config.json` 中的 `appid` 从 `touristappid` 改成你的小程序 AppID，或在开发者工具中选择自己的 AppID。
3. 默认调用远端 Ubuntu 后端：`https://jackieai.top/horoscope`。
4. 在微信公众平台配置 request 合法域名：`https://jackieai.top`。
5. 如果开发者工具仍提示域名不在合法列表，到“详情 > 域名信息”刷新项目配置后重新编译。

小程序 API 地址配置在：

```text
miniprogram/utils/config.js
```

如果临时要改成本机后端，可把 `apiBaseUrl` 改成 `http://127.0.0.1:8512`，并在项目根目录运行 `uv run app.py`。

## 测试

```bash
uv run --with fastapi --with pydantic --with pyswisseph --with pytest --with httpx pytest
```

## 环境变量

- `DEEPSEEK_API_KEY`：可选。推荐存到 macOS Keychain；为空时会尝试从 Keychain 读取，仍为空则使用规则模板输出。
- `DEEPSEEK_API_KEY_FILE`：可选。服务器部署时可指向只允许当前用户读取的密钥文件，文件内容为 DeepSeek key。
- `DEEPSEEK_MODEL`：可选，默认 `deepseek-v4-flash`；需要更强推理可设为 `deepseek-v4-pro`。
- `DEEPSEEK_CHAT_COMPLETIONS_URL`：可选，默认 `https://api.deepseek.com/chat/completions`。
- `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_CHAT_COMPLETIONS_URL`：仍兼容；如果同时配置 DeepSeek 和 OpenAI，优先使用 DeepSeek。

推荐的 DeepSeek 密钥保存方式是 macOS Keychain，不把真实 key 写入项目文件：

```bash
security add-generic-password -a "$USER" -s xingzuo.deepseek -w "你的 DeepSeek Key" -U
export DEEPSEEK_MODEL="deepseek-v4-flash"
uv run app.py
```

如果只是临时运行，也可以在当前 shell 中导出环境变量：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek Key"
uv run app.py
```

服务器部署时可以把密钥放在项目外部，并通过环境变量指向该文件：

```bash
export DEEPSEEK_API_KEY_FILE="/path/to/deepseek.key"
uv run app.py
```

不要把真实密钥写入 README、源码或提交到 git。`.env`、`.env.*`、日志和 Python 缓存已被 `.gitignore` 忽略；`.env.example` 只保留无密钥的示例默认值。

## 互动设计

首页不是单纯展示运势，而是三段式体验：

1. 星座入口：卡片展示日期范围，用户按出生日期直接选择太阳星座。
2. 星历报告：用 Swiss Ephemeris 计算真实行运行星和相位。
3. 今日星门：把最重要的相位翻译为暗面提醒、顺势动作和今日小仪式。
4. 星谕回声：用户可继续追问事业、关系、财富、身心等问题；有大模型时由 DeepSeek 基于报告回答，没有时用规则兜底。

## 后续接入建议

商业发布前需要确认 Swiss Ephemeris / pyswisseph 的 AGPL 或商业授权边界。当前代码把星历计算集中在 `xingzuo/astro_engine.py`，后续可以继续升级为更完整的本命盘、宫位、上升点、推运和返照模块。
