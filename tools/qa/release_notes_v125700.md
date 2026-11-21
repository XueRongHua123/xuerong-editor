## 雪绒的钢铁雄心编辑器 v1.25.7

修复「国家精神挂载（`country_idea_toggle`）」写进 `1939.1.1` 等后续日期块而不是国家开局顶层 `add_ideas`、并把结尾括号 `}` 粘连到 ID 末尾的问题。

### 主要改进

1. **国家开局精神读写与挂载修复（`xuerong/model/idea.py`）**
   - 修复 `country_idea_toggle()` 原先盲目取文件中第一个 `add_ideas = { ... }`（如原版法国的 `1939.1.1 = { add_ideas = { ... } }` 剧本块），导致 1936 开局完全不生效的问题；同时修复追加时未换行把 `}` 粘连成 `idea_id}` 以及无块国家错包 `history = { ... }` 的语法错误。
   - 新增 `_brace_depth_at()`、`_date_block_spans()` 与 `_collect_add_ideas_blocks()`：读取与挂载优先匹配顶层（深度 `0`）且位于日期块之外的 `add_ideas = { ... }`；不存在顶层块时在首个日期块之前自动新建标准顶层 `add_ideas = { ... }`，并在写入时补全换行与缩进；移除逻辑同步支持全文件清理及处理粘连闭合括号的旧行。

2. **回归防线锁定（`tests/test_submod_e2e.py`）**
   - 在 `test_16` 中增补含前置 `1939.1.1 = { add_ideas = ... }` 与后置顶层 `add_ideas = ...` 的国家历史读写回归用例（及无 `add_ideas` 国家新增顶层块校验）。
