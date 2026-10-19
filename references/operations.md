# 操作、数据和移交

本文件的plan/render/naming命令用于展示类模式。先按SKILL.md确认模式；剧情模式读取story-montage.md，共用inventory/review/cut，不把角色排列器当作剧情蒙太奇工具。

## 安装与前置引导

随包 `install.cmd` 安装成功后自动输出使用步骤，`install.ps1 -Destination <目标技能文件夹>` 可指定安装位置。调用 `run.cmd start` 可再次显示。制作前先执行 [路径准备流程](startup-workflow.md)，确定用户母片路径和本批工作目录；制作文件不写到技能安装目录。

## 交给其他 agent

完整解压 ZIP，保留 `role-showcase-remix` 文件夹结构。把该目录的 `SKILL.md` 路径交给执行 agent，并提供素材项目目录和本批要求。支持个人技能目录的环境可把整目录复制进去；不需要在线安装软件。启动示例：

```powershell
$skill = 'D:\skills\role-showcase-remix'
$project = 'D:\视频项目\批次001'
& "$skill\run.cmd" doctor --full
& "$skill\run.cmd" init --project $project
# 用户放好视频到项目内“母片”后
& "$skill\run.cmd" inventory --project $project
& "$skill\run.cmd" review --project $project --asset id245A
& "$skill\run.cmd" review --project $project --asset id245A --boundary 120 240
```

示例路径、ID、帧号、命名均需替换，不是当前任务的默认事实。`inventory --source 子目录` 可选择项目内其他源目录。完整帮助：`run.cmd --help` 或 `run.cmd 命令 --help`。路径可包含中文及空格。包不读取当前工作目录之外的隐式项目；每条命令明确传 `--project`。

## 配置 `.remix/batch.json`

`init` 生成可编辑 JSON，只有新项目执行一次，已有配置不覆盖。

| 字段 | 含义 |
|---|---|
| segments_per_video | 每条固定片段数，用户选3或4；脚本支持正整数 |
| max_uses | 本批每个片段最多使用几次，默认3 |
| exact_uses | false表示上限；true表示每片段必须用满max_uses |
| target_count | 明确条数；null按 `floor(片段数×上限÷组大小)` 尝试，不保证其他约束下可行 |
| unique_sets | 相同片段集合只换顺序是否禁止，默认true |
| unique_pairs | 同一对片段跨成品是否只能搭配一次，默认false |
| distinct_sources | 每条是否必须来自不同母片，默认false |
| balance_positions | 每片段在各位置次数相差不超过1，默认false |
| fixed_videos | 固定开头几条的片段ID序列，如 `[["a-01","b-02","c-01"]]`，样片包含在总数中 |
| seed | 随机搜索种子，默认0 |
| output_width/output_height | 默认1280×720；横竖方向须与用户确认，宽高用正偶数 |
| output_fps | 分数形式帧率，如30/1、30000/1001 |
| crf/preset/audio_bitrate | 默认18/medium/192k，输出H.264与AAC |
| allow_missing_audio | 默认false，缺音拒绝；用户明确允许后true补静音 |
| preserve_original_audio | 默认true，本工具仅支持跟随片段保留原声 |
| verify_mean_ssim | 每片段平均画面相似度阈值，默认0.98 |
| verify_boundary_ssim | 独立真实源首末帧相似度阈值，默认0.95 |
| verify_audio_correlation | 零时移每声道音频相关阈值，默认0.98 |
| reuse_outputs | 可选视频ID→项目内文件路径，需对应.remix.json证据匹配，不能复用任意未知视频 |

改变配置须重跑plan生成新方案，render只使用plan.json锁定的配置，不读取后来改动的batch.json。

## 区间草案 `.remix/segments.json`

从实际 `assets.json` 读取 asset_id 和清单SHA256。SHA256可用包内Python `hashlib`，或PowerShell `Get-FileHash -Algorithm SHA256` 并转为小写。帧从0开始，左闭右开；包含首帧，不包含end_frame_exclusive。

```json
{
  "source_manifest_sha256": "实际assets.json的64位小写SHA256",
  "segments": [
    {"segment_id":"稳定资产ID-01", "asset_id":"实际资产ID",
     "display_id":"id245A-01", "role":"角色甲（含变身）",
     "start_frame":0, "end_frame_exclusive":120},
    {"segment_id":"稳定资产ID-02", "asset_id":"实际资产ID",
     "role":"角色乙", "start_frame":120, "end_frame_exclusive":240}
  ]
}
```

允许不纳入片头片尾，但必须在审阅说明中登记排除范围与原因。区间不能重叠；当前cut工具只接收连续角色区间，`exclusions` 非空会拒绝。需要删除角色内部片段时先明确编辑要求并形成新的连续源素材及审阅方案，不能声称此工具已支持任意内部编辑。不同母片的display_id不得冲突，冲突时先给清单明确唯一展示ID。相同内容哈希只入库一次；重复路径不增加可用额度。

用户确认草案后操作（human-text必须替换为真实授权）：

```powershell
& "$skill\run.cmd" approve --project $project --stage cut --artifact .remix/segments.json --human-text '用户对当前区间草案的实际授权原文'
& "$skill\run.cmd" cut --project $project --only id245A
# 用户确认样片切分标准后
& "$skill\run.cmd" cut --project $project
& "$skill\run.cmd" plan --project $project --budget-seconds 30
& "$skill\run.cmd" plan-audit --project $project
# 展示组合方案后记录真实授权
& "$skill\run.cmd" approve --project $project --stage render --artifact .remix/plan.json --human-text '用户对当前组合方案的实际授权原文'
& "$skill\run.cmd" render --project $project --only 01
& "$skill\run.cmd" verify --project $project --only 01
# 确认该样片标准；同一最终方案已授权时不再重复批准
& "$skill\run.cmd" render --project $project
& "$skill\run.cmd" verify --project $project
```

plan使用有限随机搜索，超时未找到不能断言数学无解。先核对容量 `条数×组大小≤片段数×上限`；严格用满还需等号。不得自动降低要求。增加搜索预算或调整约束需符合用户授权。

## 命名

```powershell
& "$skill\run.cmd" naming --project $project --id-prefix id310 --material-name 角色展示变身 --category K4 --tag 外扒混剪 --fixed-suffix sgl --size-label 720
& "$skill\run.cmd" approve --project $project --stage rename --artifact .remix/naming.json --human-text '用户批准当前命名对照的实际原文'
& "$skill\run.cmd" rename --project $project
& "$skill\run.cmd" verify --project $project
```

命名示例：`id310-角色展示变身迭A-K4-外扒混剪-AI视频-角色展示-laizx-songxb-sgl-720.mp4`。迭代字母A..Z、AA..AG按方案顺序递增，不从旧文件名猜序号。来源名字按母片倒数第二个连字符字段初步提取，如 `...-laizx-1280.mp4`；必须逐项核对。格式不一致或缺失时写项目内 `author-map.json`，内容 `{"实际asset_id":"laizx"}`，naming加 `--author-map author-map.json`。不把角色中文名代替来源名字。来源为sgl且固定后缀也为sgl时可能出现两次，按用户规则保留，不能擅自全局去重。

## 尾帧修订

创建 `.remix/revision.json`，成品SHA256取rendered.json当前值：

```json
{"video_id":"07","trim_tail_frames":2,"reason":"去掉纯文字尾帧","output_sha256":"实际当前成品SHA256"}
```

```powershell
& "$skill\run.cmd" approve --project $project --stage revise --artifact .remix/revision.json --human-text '用户批准该条尾帧修订的实际原文'
& "$skill\run.cmd" revise --project $project --video 07 --trim-tail-frames 2 --reason 去掉纯文字尾帧
& "$skill\run.cmd" verify --project $project --only 07
```

trim-tail-frames是最后片段的**真实源帧数**，不等于输出30fps帧数。累计修订以记录中已有裁尾为基础。不能裁掉整个片段。修订保留原成品备份，从源重渲染，不重复编码旧成品，不增加片段使用次数。

## 记录和恢复

`.remix/assets.json`母片；`manifest-history`母片清单版本；`segments.json`批准角色边界；`segments-cut.json`切分结果；`plan.json`完整方案；`rendered.json`实际生成清单；`usage.json`实际有效输出使用次数；`validation`技术报告；`naming.json`命名对照；`approvals.json`授权记录。可读方案在`混剪/组合方案/方案.md`，命名对照在`混剪/命名方案/方案.md`，逐帧图片在`拉片审阅`。

中断后重复同一命令复核匹配文件并续作，遇到未知/不匹配输出拒绝覆盖。不要删除账本来绕过审批或哈希检查。重新规划后，旧输出与新方案不同需先保留旧批并用新项目/版本执行；不能把一个项目混成两个配额批次。

## 随包工具和自测

工具清单、来源、许可证见 [运行时](runtime.md)。自测使用合成素材，不访问当前母片。运行包内Python执行 `scripts/test_asset_ops.py`、`scripts/test_planner_ops.py`、`scripts/test_render_ops.py`、`scripts/test_cli_e2e.py`。自测临时文件在包目录`_tests`或系统临时目录；包目录需可写，可先解压到普通工作目录。

技能元数据自检：包内Python执行 `scripts/check_skill.py`。`tools/build_runtime.py`用于维护者联网重建运行时，保留PyPI轮子摘要检查和HTTPS证书验证；正常离线执行无需下载或重建。


## FilmCraft可编辑时间线

已确认展示计划可用filmcraft-project生成工程、filmcraft-export原生导出；详见[接入模块](filmcraft-integration.md)。filmcraft-doctor核对随包CLI。原生成品与原FFmpeg成品是同一方案的替代版本，不额外计次；选择最终版本后再命名。


## 问答后自动制作

默认入口见[自动流程](automatic-workflow.md)。auto-intake读取Agent整理的本批回答并返回缺失问题；完整实际拉片、边界和检查点就绪后auto-produce自动切分、排列、FilmCraft工程与原生导出、原生最终交付、命名和复核。filmcraft-deliver独立验证原生成品并写入最终账本。用户不需要填写JSON或执行命令。
