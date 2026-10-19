# 角色展示与剧情混剪技能

面向 Windows x64 的 Codex / Agent 技能：通过问答理解需求，拉片整理素材，制作混剪，并按需进入英雄定格与文字设计。

| 你想做什么 | 从这里开始 |
| --- | --- |
| **安装技能** | [下载完整稳定包](https://github.com/William0702/role-showcase-remix/releases/latest) → 解压 → 双击 **install.cmd** |
| **学习实际使用过程** | [左侧 Agent 提问、右侧用户回复](https://github.com/William0702/role-showcase-remix/blob/main/docs/testing/showcase-qa.zh-CN.md) |
| **了解流程与蓝图** | [文档导航](https://github.com/William0702/role-showcase-remix/blob/main/docs/README.md) |
| **维护和迭代技能** | [目录、命名与发布规范](https://github.com/William0702/role-showcase-remix/blob/main/docs/guides/maintain-and-release.zh-CN.md) |

## 安装后怎么用

新一轮 Codex 对话中发送：

```text
使用 $role-showcase-remix。
母片目录：[填写你的视频文件夹]
本次目标：[说明你要制作什么]
请先梳理这次需求，缺失内容分轮问我，项目目录由你整理。
```

完整包包含运行时与工具，安装时检查 FilmCraft 并自检。通常只下载一个 **windows-x64.zip**；GitHub 自动生成的 **Source code** 是开发源码。详见 [安装与更新说明](https://github.com/William0702/role-showcase-remix/blob/main/docs/guides/install-and-use.zh-CN.md)。

## 哪些已经验证

| 模块 | 当前状态 |
| --- | --- |
| 展示混剪 | 已有原声制作测试与实际问答记录；内容理解和核听须实际完成 |
| 剧情共创 | main 的 1.8.0 开发版已整理逐步确认、双方案和独立剪辑师流程，**真实成片链路待测** |
| 英雄定格 | 成片定稿后可选，逐项确认；图像设计依赖执行环境的实际能力 |
| 去 BGM | 盘点和提取不等于音乐分离；历史分离样段未获用户通过 |

**稳定安装包与 main 开发源码分开维护。** 推送新流程文档不代表已发布稳定版，也不代表测试通过。当前稳定版内容以 Release 为准。

## 仓库怎么读

- **docs/**：给用户看的指南、演示与测试资料。
- **SKILL.md、references/、agents/**：Agent 使用的技能入口与执行规则。
- **scripts/、tools/**：运行代码及工具元信息；完整运行时随 Release 分发。
- **publishing/、.github/**：维护者的构建与发布工具。
- **CHANGELOG.md、licenses/、LICENSE**：版本记录及许可。

运行入口保留在根目录以兼容安装：`install.cmd` 安装，`run.cmd` 执行工具，`update.cmd` 更新。用户不必逐个阅读技术文件。

[全部文档](https://github.com/William0702/role-showcase-remix/blob/main/docs/README.md) · [测试资料](TESTING.md) · [版本记录](CHANGELOG.md) · [许可](LICENSE)
