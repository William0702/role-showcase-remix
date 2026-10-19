# 维护、版本与发布规范

## 目录分工

| 目录或文件 | 用途 | 主要读者 |
| --- | --- | --- |
| README.md | 安装、演示、流程与维护四个入口 | 所有人 |
| docs/guides/ | 安装使用、维护发布指南 | 用户 / 维护者 |
| docs/testing/showcase-qa.zh-CN.md | 左问题、右回答的实际演示 | 新用户 |
| docs/testing/showcase-transcript.zh-CN.md | 完整脱敏历史对话 | 需要追溯的读者 |
| docs/testing/showcase-test-template.zh-CN.md | 可执行的测试话术与记录表 | 测试者 |
| docs/testing/showcase-test-report.zh-CN.md | 测试结果与未完成项 | 测试者 |
| SKILL.md / agents/ | Agent 技能入口与元信息 | 执行 Agent |
| references/ | 展示、剧情、定格、音频等执行规范 | 执行 Agent |
| scripts/ | 制作、安装和更新代码 | 执行 Agent / 开发者 |
| tools/ / licenses/ | 工具元信息及第三方许可；完整运行时随 Release | 开发者 |
| publishing/ / .github/ | 构建、校验和发布 | 维护者 |
| package-manifest.json | 随包文件、版本、大小及哈希 | 安装器 / 构建工具 |

根目录的 install/run/update 启动文件为兼容现有安装路径而保留，不随文档整理改名。旧测试文件只保留跳转提示，防止已分享链接失效；统一内容只维护 showcase-* 文件。

## 命名与资料规则

- 用户资料按用途命名；测试文件统一“内容类型-资料用途.zh-CN.md”，如 showcase-test-report.zh-CN.md。
- 一份内容一个维护位置。首页只导航；原始实录、精简问答、测试模板和测试结论各司其职。
- 制作素材、机器状态、私有工程和用户路径不进仓库；公开演示须授权且脱敏。
- references 文件路径属于技能调用接口；只有同步修改全部调用与包清单、验证后才能重命名。
- 开发版本与已发布稳定版本分开说明。流程检查、技术测试、核听和用户验收分别记录。

## 版本与完整包

源码保存在 Git；运行时放完整 Release。**正式 Release 以一个完整 ZIP 分发，不再默认拆成数十个附件。** 推荐附件为完整 ZIP、SHA256SUMS.txt，以及确有用途的可选联网安装入口。不要把内部构建中间文件上传到 Assets。

已发布包内容保持不变；只允许将经校验的旧传输分片还原为同字节原 ZIP，必须验证完整 SHA256、包内清单与公开下载后，才移除旧分片。不能用此操作将开发版冒充旧稳定版。

## 发布步骤

1. 修改通用流程或代码，更新 CHANGELOG；保留未测项目和风险，个人项目偏好不直接固化为通用要求。
2. 新随包资源加入 package-manifest.json；执行 `python publishing/prepare_version.py 新版本号`，再运行 `python publishing/check_repository.py`。
3. 根据变更做必要测试，剧情流程的文档一致性不能代替真实成片测试。
4. 提交源码。待测试完成，手动触发 Actions 的 Publish stable release；工作流构建单 ZIP 并自检。不要仅因文档推送就发布未测功能。
5. 本地构建可用 `python publishing/build_release.py --runtime-from 完整技能目录`；dist 不提交 Git。构建包只包含清单文件，不扫描用户制作项目。
6. 用户通过 update.cmd 更新已发布稳定版，保护修改并保留备份。

Release 附件整理使用 Consolidate existing release assets 工作流，适用于已存在的历史分片发布；不是普通发版步骤。

## 许可与一致性

自编脚本按根目录 LICENSE；第三方运行时、FilmCraft、字体等保留各自许可，见 licenses 和 tools 元信息。完整包不能把第三方全部统称 MIT。SHA256 用于损坏与一致性校验，不等于独立数字签名。
