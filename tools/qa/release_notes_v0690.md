## 雪绒的钢铁雄心编辑器 v0.69.0

AI 面板支持流式输出。

### 变化

- 发送后文字**逐字出现**，不再等整段返回（实测首片段 0.2 秒内到达，整段 651ms）
- 「发送」旁多一个「停止」按钮（只在请求中显示），点一下保留已收到的部分
- 支持四个提供商：OpenAI 兼容 / DeepSeek / Ollama（走 `/chat/completions`）、Anthropic（`/messages` SSE）、Gemini（`streamGenerateContent?alt=sse`）
- 关闭流式走的是旧的整段接口，配置错误时仍能看到具体 HTTP 报错

### 实现

- 后端 `ai_chat_stream(cfg, prompt, context, emit)` 逐块解析上游 SSE，`_ai_stream()` 用 `text/event-stream` 推给前端
- 前端用 `ReadableStream` + `AbortController`，按 `

` 分帧，`data: {"d": "..."}` 追加，`data: {"end": true}` 收尾
- 流式中断（网络/超时）会给 `end.ok=false` 并带上错误信息

### 验证

- `qa/test_v069_stream.py`：本地 mock OpenAI SSE，Content-Type 正确、5 个片段逐个到达、拼装后等于原文、
  首片段 <2s、有结束标记，7 项全通过；测完自动还原 `ai_config.json`
- `qa/probe_v069.mjs`：界面逐帧快照 `你好` → `你好，这是` → … → 完整句，meta 显示「✓ 651ms · 流式」；
  二次请求 150ms 后点停止，保住已收到的"你好，这是"并显示「已停止」，0 报错
- 视觉巡检 27 状态 × 双主题 × 两档视口全绿
