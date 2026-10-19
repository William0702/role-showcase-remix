# GitHub安装、更新与版本回退

公开仓库：https://github.com/William0702/role-showcase-remix 。源码在main，完整Windows x64技能与依赖在GitHub Releases。不要把只有源码的Git目录当作完整离线安装。

首次安装：下载源码，运行install-latest.cmd；或下载稳定Release中的完整ZIP，解压后运行install.cmd。无需GitHub账号；默认目录为CODEX_HOME/skills/role-showcase-remix，未设置CODEX_HOME则使用用户主目录下.codex/skills。

更新：在已安装技能目录运行update.cmd，选择GitHub最新稳定Release。update.cmd -CheckOnly只检查；update.cmd -Version 1.7.1可固定版本；用已发布旧版本号可回退。也可在源码目录运行install-latest.cmd -Update。自定义目录追加-Destination。

只下载公开的固定仓库Release，先核对ZIP的SHA256，再核对全部包文件，使用下载包自带Python运行安装器。安装器保护本地修改、保留未知文件，并在升级前备份；程序自检成功后输出使用步骤。校验用于检测损坏和版本一致性，并非独立数字签名。失败保留缓存，不强删技能。备份位置为技能父目录的上级/skill-backups。

更新按用户调用执行，不注册后台任务、不擅自更新正在执行的生产任务。技能代码更新不改项目素材或项目工程。main可能包含尚未发布修改，普通用户以最新稳定Release为准。发布新版本后，所有用户再次执行更新命令即可同步。

完整包可用单ZIP或Release分片发布，安装/更新器自动选择：下载并核对各分片SHA256，流式合并后再次核对完整ZIP，再按原流程安装。分片只是传输方式，装好的依赖和功能相同；不要求用户另装分片工具。离线用户可用Release附带的assemble-offline.ps1重组。
