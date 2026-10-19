# FilmCraft内置软件、自动安装及自检

技能包包含完整官方FilmCraft 0.7.2 Windows x64便携包（GUI＋CLI），不是只有命令行工具。文件在tools/software，软件归档已与官方SHA256SUMS.txt核对，版本和来源在filmcraft-release.json；原许可保留在便携归档及licenses/FilmCraft。

## 安装技能之前

install.cmd/install.ps1先校验包文件，并查找本机FilmCraft：运行中的FilmCraft路径、App Paths注册项、Program Files、用户Programs目录、PATH及本技能管理的便携目录。须同时存在GUI和CLI，版本匹配、不低于0.7.2，命令接口可用，实际原生自检通过，才判定可复用。不能只凭文件夹或Launcher存在判定软件已安装。已有可用版本不卸载、不覆盖。

没有可用本地软件时，自动解压随包官方完整程序到用户LOCALAPPDATA/ArtCraft/FilmCraft/0.7.2，属于独立可运行的便携安装，不改Program Files、不要求系统MSI安装或管理员权限，不自动启动交互窗口。先在独立临时目录验证GUI/CLI和实际导出，再复制到最终软件目录。已有不完整的受管理目录保留并明确报告，不能覆盖未知文件冒充修复。

若随包软件归档缺失，自动从https://github.com/storytold/filmcraft/releases/download/v0.7.2/获取同版官方便携包和SHA256SUMS.txt，核对预先固定的SHA256后才使用。缓存已具有匹配哈希时可复用。固定经过本技能验证的0.7.2，不擅自用其他镜像或未验证最新版本。缺归档可以补齐；哈希不符则停止，不能放宽校验。离线且归档/缓存均无时如实报告缺项。

安装完成保存.software/filmcraft.json，记录实际GUI/CLI路径、版本、哈希、安装来源及自检结果。其为本机状态，不是源包校验文件。制作入口读取该记录，程序发生变化后重新检测与自检；明确指定CLI属于高级手动覆盖，默认自动模式使用已验证完整软件。

## 自检范围

GUI --version和CLI --version、命令目录、真实项目创建、素材导入、视频及原声轨放置、原生H.264/AAC导出，并由技能的独立工具核对全部测试帧、首末帧和双声道原声。使用合成测试素材，不打开用户正在编辑的工程，不宣称这些检查代替真实成品的内容验收。

```powershell
& "技能目录\run.cmd" software-setup
# 指定独立便携安装目录（默认仍先检测本地软件）
& "技能目录\run.cmd" software-setup --software-dir "用户软件目录"
```

使用者无需执行上述命令；安装及首次制作时自动准备。首次没有软件可能需要等待解压与自检；不把等待当作安装成功。

## 已有技能更新

```powershell
& "技能目录\install.ps1" -Upgrade
```

升级前检查旧技能全部清单文件，旧技能若有用户修改则保留并报告差异，不直接覆盖。已知未修改版本先完整备份到个人技能目录上级的skill-backups，再更新随包文件、自检并写软件状态。未列入清单的用户文件保留。其他人的电脑各自检测与安装，不能复用本机保存的绝对路径。

当前软件包仅Windows x64，其他平台需要相应发布包及实际验证，不能运行此内置Windows程序。
