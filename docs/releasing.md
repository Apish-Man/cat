# 开发与发布

## 日常开发

长期维护 `main`。每次功能或修复从最新的 `main` 开短分支，例如 `feat/new-toy` 或 `fix/walk`。在分支上开发、测试，通过 PR 合回 `main` 后即可删除该分支。发布历史通过版本标签保留。只有需要同时给旧版提供补丁时，再从对应标签开维护分支。

## 准备版本

下面以 Windows 便携版为例。Mac 预览使用独立的应用版本号、导出配置和 arm64 验收流程，详见 [Mac 预览版实现方案](implementation-v1.3.0-alpha.1.md)。

修复递增补丁号（例如 1.2.1），新增兼容功能递增次版本号（例如 1.3.0）。同步更新 `catmate/__init__.py`、README 和 `docs/releases/v版本号.md`，将改动合入 `main`。在选定的提交上创建标签，例如 `git tag -a v1.2.1 -m "CatMate v1.2.1"`。

在干净的 Windows x64 工作目录检出这个标签，按 README 的「构建与验证」运行构建、单元测试、Qt 检查及独立 EXE 检查。运行下面的 PowerShell 命令打包，版本号取自已检出的标签。

```powershell
$tag = git describe --tags --exact-match HEAD
if ($LASTEXITCODE -ne 0) { throw "请先检出发布标签" }
$zip = "dist/CatMate-$tag-windows-x64.zip"
Compress-Archive -Path dist/CatMate -DestinationPath $zip -Force
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($zip))" | Set-Content "$zip.sha256" -Encoding ascii
```

## 上传到 GitHub

推送 `main` 和本次版本标签，再把 ZIP 与校验文件作为 Release 附件上传。以下命令沿用上面的 `$tag` 和 `$zip`，需要已登录的 GitHub CLI。

```powershell
git push origin main
git push origin $tag
gh release create $tag $zip "$zip.sha256" --verify-tag --draft --title "猫在 $tag" --notes-file "docs/releases/$tag.md"
```

打开草稿，确认标签、说明和两个附件，点击 **Publish release**。用户下载 Windows ZIP 即可运行。仓库可见性可在 GitHub 的仓库设置中单独调整。参见 [GitHub Release 命令说明](https://cli.github.com/manual/gh_release_create)。
