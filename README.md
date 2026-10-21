# 角色展示与剧情混剪技能

面向 Windows x64 的 Codex / Agent 技能：通过问答理解需求，拉片整理素材，制作混剪，并按需进入英雄定格与文字设计。

| 你想做什么 | 从这里开始 |
| --- | --- |
| **安装技能** | [下载完整稳定包](https://github.com/William0702/role-showcase-remix/releases/latest) → 解压 → 双击 **install.cmd** |
| **学习实际使用过程** | [左侧 Agent 提问、右侧用户回复](https://github.com/William0702/role-showcase-remix/blob/main/docs/testing/showcase-qa.zh-CN.md) |
| **了解流程与蓝图** | [文档导航](https://github.com/William0702/role-showcase-remix/blob/main/docs/README.md) |
| **维护和迭代技能** | [目录、命名与发布规范](https://github.com/William0702/role-showcase-remix/blob/main/docs/guides/maintain-and-release.zh-CN.md) |

## 复制给 Agent：安装技能

在支持本地文件和命令执行的 Codex / Agent 中复制发送以下内容（当前完整包支持 Windows x64）：

```text
请帮我安装这个 GitHub 仓库的 role-showcase-remix 技能：
https://github.com/William0702/role-showcase-remix

先阅读仓库 README 和安装说明，检查我的系统及已有安装。
请使用 Releases 中的最新稳定版完整 Windows x64 安装包，按仓库安装流程执行；不要把仅含源码的仓库 ZIP 当作完整技能包。
安装目录遵循当前环境的 CODEX_HOME；未设置时使用当前用户的 .codex/skills。
如已安装，按仓库更新流程处理，保留本地修改、备份和制作项目。
安装后执行依赖、包文件和 FilmCraft 自检，告诉我实际版本、安装路径、检查结果与未完成项，再给出开始使用的步骤。
```

## 复制给 Agent：更新技能

已安装用户可以复制发送：

```text
请按照仓库说明，将本机 role-showcase-remix 更新到最新稳定版：
https://github.com/William0702/role-showcase-remix

先检查实际安装位置和版本，再使用仓库的更新入口。
保留本地修改、备份及制作项目，不直接覆盖冲突文件。
更新后执行自检，告诉我实际版本、检查结果和下一步使用方法。
```

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
| 剧情共创 | 1.8.0 已发布供使用者本地测试，已整理逐步确认、双方案和独立剪辑师流程，**真实成片链路待测** |
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


## v1.8.1 性能优化

本版新增两项默认启用的项目内技术缓存，减少重复工作，不改变现有制作流程：

| 优化 | 实际作用 |
| --- | --- |
| 元数据与逐帧时间戳缓存 | 同一媒体内容、工具和解析实现未变时，复用探测结果 |
| 成功完整核验结果复用 | 原生导出后，交付阶段在完整绑定一致时复用已通过的画面与双声道技术报告 |

绑定包含源片段、成片、方案、顺序、输出参数、阈值、工程/兼容素材、工具和代码等；变化时重新计算。损坏或缺失的缓存退回实际检查，失败结果不作为通过证据。缓存放在使用者项目的 `.remix/cache`，不随技能包分享。

两条已有成片的“核验与交付”实测：

| 测试状态 | 耗时 |
| --- | ---: |
| v1.8.0 原流程 | 97.49 秒 |
| 优化后首次运行 | 55.35 秒 |
| 缓存命中后再次运行 | 5.04 秒 |

这不是重新编码测试，不包含拉片、方案共创、用户等待或整批生产；不能把上述差异外推为整体制作提速倍数。原本 29 项缓存测试加上发布复核新增的 4 项边界回归，共 33 项缓存测试，并配合原有制作回归检查行为与兼容性，不代表剧情成片已经验收。

原有审批、配额、完整内容审阅、接点查看和实际核听要求均保留。最终 `verify` 仍做完整验证；兼容转码共享、并行导出与硬件编码尚未在本版实现。

需要排障时使用 `filmcraft-export --force-recheck` / `filmcraft-deliver --force-recheck`，或对当前进程设置 `REMIX_DISABLE_CACHE=1`。详见 [缓存与强制复检说明](https://github.com/William0702/role-showcase-remix/blob/main/references/performance-cache.md)。


## 1.9.0 开发源码：双方向流程蓝图

[查看展示类与剧情 A/B 两张可视化蓝图](https://github.com/William0702/role-showcase-remix/blob/main/docs/guides/workflow-blueprints.zh-CN.md)。

展示类保留已授权自动制作及逐步确认两种方式；剧情类收紧为完整理解→全池内容索引→理解复核→全池筛配→方案与代表样片→同规则批量→定点返修。先判断内容关系，不为覆盖强配或强凑蒙太奇；动态审片、核听与用户认可分别记录。

本节对应 main 上的 1.9.0 开发源码，尚未发布完整 Release；运行脚本与 v1.8.1 性能缓存保持原样。新流程仍待真实整轮验证，不宣称已提速或蒙太奇通过。普通安装与更新继续使用最新已发布 Release。
