# 离线运行时与来源

本包提供全部实际运行依赖：

| 文件/模块 | 版本 | 用途 |
|---|---|---|
| tools/windows-x64/python/python.exe | Python3.12.10 Windows amd64 embed | 运行脚本，不需要安装Python |
| python/Lib/site-packages/numpy | 2.3.5 | 切分音频数值核验 |
| python/Lib/site-packages/PIL | Pillow11.3.0 | 全帧联系页生成 |
| python/Lib/site-packages/yaml | PyYAML6.0.3 | 离线技能结构自检 |
| tools/windows-x64/ffmpeg.exe | 9.0.2 Gyan essentials | 解码、裁剪、重排、编码、图像与声音核验 |
| tools/windows-x64/ffprobe.exe | 同版 | 帧时间戳、流和格式清单 |
| scripts/common.py | 随包源码 | 路径、哈希、原子JSON和授权记录 |
| scripts/asset_ops.py | 随包源码 | 入库、全帧联系页、连续区间切分 |
| scripts/planner_ops.py | 随包源码 | 有限搜索、硬约束、命名与回滚 |
| scripts/render_ops.py | 随包源码 | 原声拼接、末帧保留、核验与修订 |
| scripts/remix.py/run.cmd/run.ps1 | 随包入口 | 命令行调度、运行时检查 |
| scripts/check_skill.py | 随包源码 | 技能元数据与引用资源自检 |
| tools/build_runtime.py | 随包源码 | 联网重建同版运行时；日常使用无需执行 |

构建来源和原始下载SHA256在 `tools/download-provenance.json`。包内文件完整性在 `package-manifest.json`，执行doctor --full核对；ZIP另附SHA256。清单用于检测缺失/变更，不是数字签名或来源认证。

Python来自 [Python官方下载](https://www.python.org/downloads/release/python-31210/)，NumPy/Pillow使用PyPI对应Windows wheel，原许可证随dist-info及Python目录保留。FFmpeg来自 [官方列出的Windows构建](https://ffmpeg.org/download.html) 的 [Gyan9.0.2发布](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2)。保留 `licenses/FFmpeg-LICENSE` 与构建配置/第三方版本说明 `licenses/FFmpeg-README.txt`，FFmpeg匹配源码commit946fcce07b归档在 `tools/sources/ffmpeg-9.0.2-source.tar.gz`。该源码是FFmpeg本体，不能声称它包含Gyan静态链接的全部第三方依赖源码；完整重建需按构建说明获取这些上游依赖。

FFmpeg构建为GPLv3，Python、NumPy、Pillow许可证见各随包文件。分发包保留原许可证和来源说明。自编业务脚本采用MIT，见licenses/Remix-scripts-MIT.txt，第三方组件继续适用各自许可证。

本工具包不包含AI模型、账号、API密钥、素材或当前项目成品。其他agent需要其已有图像理解与对话环境。没有联网也能执行包内CLI，图像理解是否离线取决于执行agent自身环境。


FilmCraft可选引擎：tools/windows-x64/filmcraft-cli.exe（0.7.2 Windows x64），来源与哈希见tools/filmcraft-provenance.json，MIT OR Apache-2.0及字体OFL许可保留于licenses/FilmCraft。适配器scripts/filmcraft_ops.py创建工程并调用原生导出，说明见filmcraft-integration.md。CLI随包提供，不依赖Launcher运行，不调用远端AI。


完整FilmCraft GUI/CLI软件：tools/software/filmcraft-0.7.2-windows-x64-portable.zip，官方SHA256SUMS.txt已核对；自动检测、便携安装和原生自检由scripts/software_ops.py实现，见software-workflow.md。本机已有程序优先使用，随包程序与官方固定发布为缺软件时的自动安装来源。


离线FilmCraft API参考：references/filmcraft-official/；源码快照：tools/sources/filmcraft-0.7.2-source.tar.gz。只包含技能实现及依赖资料，不含本批视频、对话记录或实际制作工程。

第二阶段由执行Agent按[英雄定格流程](hero-freeze-workflow.md)和[动画提示词模板](hero-animation-prompts.md)问答执行；离线工具可提帧、合成和检测，艺术字需要实际可用的图像生成/编辑能力。两路提示词由图像理解/文本能力编写；不新增一个未经验证的自动CLI，不声称离线包自带图像或视频生成模型。
