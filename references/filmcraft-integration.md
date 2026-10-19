# ArtCraft / FilmCraft 接入模块

用户选择可编辑桌面工程或FilmCraft导出时使用。本次已确认安装的是ArtCraft Launcher和FilmCraft 0.7.2。Launcher负责安装管理，FilmCraft负责视频时间线；ArtCraft主程序的AI生成与本模块不同，不需要上传素材、登录账号或调用模型。

## 已实现命令

```powershell
& "技能目录\run.cmd" filmcraft-doctor
& "技能目录\run.cmd" filmcraft-project --project "本批制作目录" --only 01
& "技能目录\run.cmd" filmcraft-export --project "本批制作目录" --only 01
```

省略--only按本批方案逐条执行。CLI优先显式--cli，其次REMIX_FILMCRAFT_CLI，随后随包tools/windows-x64/filmcraft-cli.exe，再尝试本机安装和PATH。随包CLI版本0.7.2，运行时调用其commands核对能力；不依赖用户机器固定安装路径。

先完成原有角色审阅、切分、plan及plan-audit，按实际用户授权记录该方案render审批。适配器调用原审批与完整方案审计，校验源哈希，不把安装软件当作新剪辑方案的批准。

filmcraft-project：读取已批准展示方案；按照实际PTS、输出帧率和真实首末帧生成兼容媒体；保留原声，H.264 baseline CRF12＋PCM MOV，随后通过FilmCraft官方CLI创建.fcproj。每片段放置链接视频与原声，位置用整数帧，长度用254016000000 ticks/秒。核对视频及音频的顺序、帧范围、速度、反放、增益和静音状态；实际渲染每段入口，拒绝offline占位帧。

工程在混剪/FilmCraft/条号，映射在.remix/filmcraft.json。工程引用同文件夹的compat媒体，不把媒体嵌入工程。移交时整个目录及所需项目素材一起复制，迁移后重新检查或用FilmCraft重新链接路径；单独复制.fcproj不能保证媒体在线。重复构建不覆盖已有工程；需要另一个版本时使用独立批次目录或先明确备份位置。

filmcraft-export：再次核对计划、工程及兼容媒体哈希，使用FilmCraft原生引擎导出H.264/AAC，再用已有FFmpeg核验所有输出帧、真实源首末、双声道原声零位移对应与总帧数。失败保留诊断文件，不登记合格成品，不放宽阈值。导出报告native-validation.json；这是一份已有方案的替代版本，不增加片段计次，原rendered/usage与最终命名交付不自动改动。用户确认采用原生成品后，明确选择交付版本再命名，不重复算条数。

## 兼容素材要求

导入成功不代表可解码：必须实际渲染，拒绝offline或unreadable占位帧。按本模块生成标准H.264 baseline与PCM兼容素材，检查转换后的全部输出帧、真实首末帧和原声音轨，核验通过后才能导出并登记合格。

## 可编辑工程与剧情能力边界

当前三个命令覆盖完整角色片段的展示方案，不把剧情决定表当作展示plan。FilmCraft本身有时间线、转场、音频和MCP，但本适配器尚未实现剧情决定表、J/L-cut及蒙太奇转场映射。剧情仍按原模块逐条编制脚本或FilmCraft命令清单，完成接点预演和用户验收后才导出；不得声称已通过剧情真实全流程测试。FFmpeg原渲染与核验保留，可继续选择原引擎。

MCP可用随包filmcraft-cli.exe mcp启动headless会话。bridge连接正在运行的桌面须由filmcraft --control PORT启动；本次未修改运行中的GUI或用户MCP配置。直接CLI已足够完成批量工程与导出，不要求用户额外配置MCP。

## 官方资料

- https://github.com/storytold/artcraft
- https://github.com/storytold/filmcraft （docs/agents.md、docs/control-protocol.md、docs/project-files.md、apps/filmcraft-cli）
- https://github.com/storytold/craft-launcher
- https://github.com/storytold/artcraft-services
- https://github.com/storytold/craft-fonts

使用到的离线接口文档在references/filmcraft-official，完整当前FilmCraft源码快照在tools/sources/filmcraft-0.7.2-source.tar.gz；运行不依赖制作项目目录或对话记录。源码快照不包含Git历史、Issue或全部发布附件。CLI来自本机已安装0.7.2，版本和SHA256见tools/filmcraft-provenance.json；文件哈希检查不等于发布签名验证。


## 自动最终交付

filmcraft-deliver独立验证已导出的原生视频，复制到成品目录，写入rendered/usage和旁路记录；保留原版本和历史账本。auto-produce将本模块串入问答后的自动制作，默认以原生成品作最终交付。已对应的工程和视频可断点复用，不覆盖不同哈希文件，改名后再运行仍保留最终文件名与计数。
