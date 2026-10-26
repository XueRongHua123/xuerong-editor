## 雪绒的钢铁雄心编辑器 v0.73.1

包体瘦身：exe 24.2 MB → **20.1 MB**，zip 23.9 MB → **19.8 MB**。

### 砍了什么

用 PyInstaller 拆开 exe 看，解压后 46.4 MB，最大的单项是 **Pillow 的 AVIF 插件 `PIL/_avif.pyd` 7.89 MB**——
这个项目只用 `Image.open / convert / frombytes / save / resize`，从来不碰 AVIF。

在打包参数里加 `--exclude-module PIL._avif` 后，exe 少了 4.1 MB（压缩后）。

### 包内现在的构成（解压 42 MB → 压缩 20.1 MB）

| 项 | 大小 | 说明 |
|---|---|---|
| python312.dll | 6.95 MB | Python 运行时，省不掉 |
| libcrypto-3.dll + libssl-3.dll | 6.02 MB | urllib 的 HTTPS（AI 接口要用） |
| PIL/_imaging.pyd | 2.66 MB | 地图图层、图标处理 |
| PYZ.pyz | 2.30 MB | 打包后的 .pyc |
| tcl86t + tk86t | 3.43 MB | 「添加 mod」的文件夹选择对话框 |
| mascot/*.png | 7 MB | 8 套皮肤（功能资产） |
| base_library.zip | 1.33 MB | 标准库 |

### 还能再砍吗

- Tk（3.4 MB）能砍，但要自己写一个文件夹选择器的替代方案（比如读环境变量或手输路径），体验会退化，暂时留着
- 皮肤 PNG（7 MB）能压到约 3 MB，但会伤画质
- 剩下的都是运行时与加密库，砍不动

### 验证

启动新 exe（20.1 MB）→ `/api/map_meta` 正常返回（Pillow 仍可用）、来源列表正确、
页面含地图面板与来源下拉。
