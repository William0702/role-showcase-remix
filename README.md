# Role Showcase Remix / 角色展示混剪

Windows x64的Codex/Agent技能：素材问答、完整拉片、角色切分、排列与次数核验、FilmCraft工程及原生导出；用户定稿后可选英雄定格、文字设计和两路动画提示词。

**仓库：** https://github.com/William0702/role-showcase-remix  
**完整稳定版：** https://github.com/William0702/role-showcase-remix/releases/latest

## 首次安装

打开最新Release，下载role-showcase-remix-v版本-windows-x64.zip，解压并运行install.cmd。安装前会检查FilmCraft，没有可用版本则安装随包便携程序并执行实际导出自检。不需要GitHub账号、系统Python或另装FFmpeg。当前支持Windows x64。

默认目录为用户的.codex/skills/role-showcase-remix；设置CODEX_HOME时使用其skills目录。下一轮Codex对话可使用 $role-showcase-remix。

联网安装：下载本仓库源码ZIP，解压运行install-latest.cmd；它下载完整稳定版并校验再安装。Source code ZIP只有源码，不能直接当作已经安装好完整运行时。也可以直接发给Agent：

> 请安装 https://github.com/William0702/role-showcase-remix 的最新稳定版。先读README，使用完整Release或install-latest入口，完成运行时与FilmCraft自检，保留本地修改。

## 更新与回退

在已安装技能目录运行：

```powershell
./update.cmd
./update.cmd -CheckOnly
./update.cmd -Version 1.7.1
```

每次查询最新稳定Release、验证下载包与全部文件、检查修改、备份再升级并自检。CheckOnly只查看；Version固定已发布版本，指定旧版可回退。从源码目录也可运行install-latest.cmd -Update。自定义目录追加-Destination D:/MySkills/role-showcase-remix。

本地修改时停止，不强制覆盖；备份在目标skills目录上级的skill-backups，失败缓存保留。项目素材和工程不因更新改动。普通用户以最新稳定Release为准，main可能有未发布修改。更新按需运行，不注册后台任务。

## 使用与确认

提供本地母片或目录。Agent整理独立项目，补问分组/数量/配额/输出/命名规则，实际查看全帧及边界，再切分、组合、原生导出和核验。变身、动作、景别变化不自动算新角色。

第二阶段：用户确认成片定稿→选择是否定格→单帧确认→名称/文案/排版→样张确认→同一文字母层派生原帧图/纯绿图/透明层→逐项确认→选择绿幕文字或角色环境微动文字动画提示词→确认交付。支持单项/整批重做和恢复旧版。

展示类自动技术链已有测试；真实角色判断、完整逐帧查看与听感验收由执行Agent负责。第二阶段为Agent问答模块，艺术字需要实际可用的图像生成/编辑能力，离线包不含AI模型或账号。提示词不等于已生成动画；实际生成、抠像和追加成片另行明确。音频盘点/提取不等于已实现去BGM且完整保留对白/音效。剧情蒙太奇有独立流程，不是已验证的一键FilmCraft剧情引擎。

## 维护者：迭代发布

Git保存源码及依赖哈希，大体积运行时与软件放完整Release，不进Git。旧发布版本保留。

1. 在仓库修改通用技能及CHANGELOG，不加入个人素材、机器状态或对话。
2. 新增随包文件先加入package-manifest.json；执行python publishing/prepare_version.py 1.7.2更新版本和现有源码哈希，再执行python publishing/check_repository.py。
3. 提交推送main，Actions选择Publish stable release→Run workflow。工作流复用上一稳定版中哈希匹配的运行依赖，构建完整包并执行doctor后发布。依赖变化须提供匹配运行时，不能跳过校验。
4. 本机发布：python publishing/build_release.py --runtime-from 完整技能目录。检查dist/stage的完整包，再发布dist里的ZIP与SHA256SUMS.txt。首次版本用该本机流程建立；dist不提交Git。
5. 用户运行update.cmd同步。push/PR自动源码检查，正式发布需维护者手动触发，不随普通文档修改自动发布。

## 许可

自编脚本按MIT（LICENSE）；Python、FFmpeg、FilmCraft、字体和Python库按各自原许可，声明与来源见licenses和tools元数据。完整包保留依赖与随包源码归档，不把全部第三方运行时统称MIT。FFmpeg本体归档不代表所有静态第三方库完整重建源码，信息见运行时参考与第三方构建说明。

ZIP的SHA256及包清单用于损坏和一致性检查，并非独立数字签名。请使用本仓库正式Release。
