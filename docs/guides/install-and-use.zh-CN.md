# 安装、使用与更新

适用 Windows x64。普通用户使用完整稳定包，不需要读开发源码。

## 1. 安装

打开 [最新稳定版](https://github.com/William0702/role-showcase-remix/releases/latest)，下载名称以 **windows-x64.zip** 结尾的完整包，解压后双击 **install.cmd**。安装器准备随包运行时和 FilmCraft，并执行实际自检。

GitHub 自动生成的 **Source code (zip/tar.gz)** 只含开发源码，不是完整安装包。无需下载全部 Assets；SHA256SUMS.txt 用于校验，可选联网安装脚本是另一种入口。

默认安装到当前用户的 `.codex/skills/role-showcase-remix`；设置 CODEX_HOME 时使用其 skills 目录。新一轮 Codex 对话即可调用技能。需要联网安装时，可下载仓库源码并运行根目录 install-latest.cmd，由它获取完整稳定包；它不会把缺运行时的源码直接当成完整技能安装。

也可以发给 Agent：

```text
请安装 https://github.com/William0702/role-showcase-remix 的最新稳定版。
先读安装说明，使用完整 Release，完成依赖与 FilmCraft 自检，并告诉我安装结果。
```

## 2. 开始制作

```text
使用 $role-showcase-remix。
母片目录：[你的视频所在文件夹]
这次希望制作：[展示类或剧情类，以及你的目标]
请先梳理本次需求，缺失内容分轮问我，项目目录由你整理。
```

- 展示类：补齐数量、分组、使用次数范围、输出与命名等要求，再按授权制作。
- 剧情类：1.8.0 采用逐步共创、同素材双方案和独立审阅；**已发布供本地测试，但尚未完成真实成片测试，不是已验证的一键功能**。具体以安装版本内的说明为准。
- 成片后先确认音频与定稿，再选择是否进入英雄定格。混合音轨去 BGM 依赖另行验证的工具，不能保证完全保留对白与音效。

先看 [实际左右问答演示](../testing/showcase-qa.zh-CN.md)，要自己测试则用 [分步测试模板](../testing/showcase-test-template.zh-CN.md)。

## 3. 更新和回退

在技能安装目录运行 `update.cmd` 获取最新稳定版；`update.cmd -CheckOnly` 只查看；`update.cmd -Version 1.7.1` 选择指定已发布版本。默认保护本地修改并备份，不修改制作项目。

main 是开发源码，可能比稳定版更新；推送源码不等于发布稳定版，普通用户不需要同步 main 才能使用。
