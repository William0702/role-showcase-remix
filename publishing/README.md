# 低上传带宽的分片发布

常规构建和GitHub Actions继续使用单ZIP；build_release.py自动兼容上一稳定版是单ZIP或分片，始终核对每片和完整ZIP的哈希。

若上传单连接很慢：执行python publishing/split_release.py dist/完整ZIP，得到4MiB分片和release-parts.json。把全部分片、release-parts.json、SHA256SUMS.txt上传同一草稿Release，完整后才发布。可附带assemble-offline.ps1供离线用户组包；在线安装/更新器会自动处理，用户不需改命令。

每个分片名、大小、SHA256及原ZIP大小和SHA256写入清单。禁止缺片时发布，禁止把任意分片当作可独立安装的ZIP。版本发布后不改资产；修复后发布新版本。
