## 雪绒的钢铁雄心编辑器 v1.0.1

**自动检查更新**：不用再手动来 GitHub 看有没有新版。

### 怎么工作

1. 启动后 4 秒静默查一次 GitHub 最新 Release（不打断首屏）
2. 顶栏右侧有个版本胶囊：`v1.0.1`。有新版本时变成 `v1.0.1 → v1.0.2` 并高亮
3. 点胶囊可以手动检查（会说「已是最新版本」或「检查失败」）
4. 发现新版时弹窗显示：版本对比、发布时间、更新说明、下载按钮
5. 点「7 天内不再提示」后一周内不再自动弹

### 实现细节

| 项 | 做法 |
|---|---|
| 查什么 | `GET /repos/.../releases/latest`，只用一个请求 |
| 限流 | GitHub 未认证 60 次/小时；结果缓存 **6 小时**（内存 + `cache/update.json`） |
| 失败处理 | 网络不通、超时、404 全部静默，不弹错误 |
| 版本比较 | 按数字段比较（`1.10 > 1.9`，不是字符串比较） |
| 下载按钮 | 自动从 assets 里挑 `.exe` 那个，没有就打开 Release 页 |

### 顺带修掉两个老问题

**1. exe 里终于有版本号了**

之前代码里根本没有版本常量，程序不知道自己是谁。现在：
- 打包时 `make_release.py` 生成 `_build_version.py`（`VERSION = "1.0.1"`），作为模块打进 exe
- 打包结束自动删除临时文件，源码运行回退到 `git describe`
- 实测：exe 内 `app_info.version = 1.0.1`、`frozen = true`

**2. 附件名不再是 `default.exe`**

GitHub 的 upload API 会把 URL 里的中文名压成 `default.exe` / `_v1.0.0.zip`，用户下载下来根本认不出是什么。

现在统一用 ASCII 资产名：

```
xuerong-editor-v1.0.1.exe
xuerong-editor-v1.0.1.zip
```

（本地打包产物仍是中文名，只是上传到 GitHub 时换名。）

### 实测

```
exe 内版本: 1.0.1  frozen: True
更新检查: ok=True current=1.0.1 latest=1.0.0 newer=False
```

判断正确——当前已是最新，不会误报。
