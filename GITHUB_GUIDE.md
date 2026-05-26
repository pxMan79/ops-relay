# ops-relay GitHub 接入指南

## 📋 前置准备

### 1. 确认 Git 已安装
```bash
git --version  # 应该显示 2.x 或更高版本
```

如果未安装：
```bash
# Windows (使用 Scoop)
scoop install git

# 或者下载: https://git-scm.com/downloads
```

### 2. 配置 Git 用户信息（首次使用）
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

## 🚀 创建 GitHub 仓库

### 方式一：通过 GitHub CLI（推荐）

```bash
# 安装 GitHub CLI (gh)
# Windows: winget install GitHub.cli
# Mac: brew install gh

# 登录 GitHub
gh auth login

# 创建新仓库（私有）
gh repo create ops-relay \
  --private \
  --source=. \
  --push \
  --description "基于 Ansible + FastAPI + Vue 3 的内网服务器监控平台"

# 如果要公开仓库，去掉 --private 参数
```

### 方式二：手动创建（网页操作）

1. **打开 GitHub**: https://github.com/new

2. **填写仓库信息**:
   - Repository name: `ops-relay`
   - Description: `基于 Ansible + FastAPI + Vue 3 的内网服务器监控平台`
   - Visibility: 选择 **Private**（推荐）或 Public
   - ❌ **不要勾选** "Add a README file"（我们已有 README.md）
   - ❌ **不要勾选** "Add .gitignore"
   - ❌ **不要勾选** "Choose a license"（后续可添加）

3. **点击 "Create repository"**

4. **推送本地代码到 GitHub**:
   ```bash
   # 添加远程仓库
   git remote add origin https://github.com/pxMan79/ops-relay.git
   
   # 重命名分支为 main（GitHub 默认主分支）
   git branch -M main
   
   # 首次推送
   git push -u origin main
   ```

---

## 🔐 安全配置（重要！）

### 1. 使用 SSH 密钥（推荐）

```bash
# 检查是否已有 SSH 密钥
ls ~/.ssh/id_*.pub

# 如果没有，生成新的
ssh-keygen -t ed25519 -C "your.email@example.com"

# 复制公钥内容
cat ~/.ssh/id_ed25519.pub | clip  # Windows

# 添加到 GitHub:
# Settings → SSH and GPG keys → New SSH key → 粘贴公钥
```

测试连接：
```bash
ssh -T git@github.com
# 应显示: Hi pxMan79! You've successfully authenticated...
```

修改远程地址为 SSH：
```bash
git remote set-url origin git@github.com:pxMan79/ops-relay.git
```

### 2. 使用 Personal Access Token (PAT)

如果不想配置 SSH，可以使用 Token 认证：

1. **生成 Token**:
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - 点击 "Generate new token (classic)"
   - 勾选权限：`repo`（完整仓库访问权）
   - 生成并复制 Token

2. **推送时使用 Token**:
   ```bash
   git push https://pxMan79:YOUR_TOKEN@github.com/pxMan79/ops-relay.git main
   ```
   
   ⚠️ **注意**: 不要将包含 Token 的命令保存到脚本或历史记录中！

---

## 📦 推送后的仓库结构

你的 GitHub 仓库应该包含以下文件：

```
ops-relay/
├── .env.example              ✅ 已脱敏的模板
├── .gitignore                ✅ 排除敏感文件
├── config.yml.example        ✅ 配置模板（无真实数据）
├── Dockerfile.backend         ✅ 后端镜像定义
├── Dockerfile.frontend        ✅ 前端镜像定义
├── docker-compose.yml         ✅ 开发环境编排
├── docker-compose.prod.yml    ✅ 生产环境编排
├── deploy.sh                  ✅ Linux 部署脚本
├── deploy.bat                 ✅ Windows 部署脚本
├── nginx.conf                 ✅ Nginx 配置
├── backend/                   ✅ FastAPI 后端代码
├── frontend/                  ✅ Vue 3 前端代码
└── README.md                  ✅ 完整文档
```

**已排除的敏感文件**（不会出现在仓库中）:
- ❌ `config.yml` （真实配置，含服务器 IP、密码等）
- ❌ `.env` （含 API Token、JWT Secret 等）
- ❌ `*.xlsx` （Excel 报表，可能含敏感数据）
- ❌ `monitoring.db` （SQLite 数据库）
- ❌ `~/.ssh/*` （SSH 密钥）

---

## 🔄 后续工作流

### 日常开发流程（单人维护）

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 开发和提交
git add .
git commit -m "✨ Add new feature description"

# 3. 直接推送到 main
git push origin main
```

### 发布版本

```bash
# 创建版本标签
git tag v2.0.0
git push origin v2.0.0

# 或使用 GitHub Releases
gh release create v2.0.0 \
  --title "v2.0.0 - Docker化部署" \
  --notes "- ✅ 完整 Docker 支持
- ✅ 生产环境优化
- ✅ 脱敏处理和安全加固"
```

---

## 🎯 部署到 10.0.0.15 服务器

### 方式一：直接在服务器上克隆

```bash
# SSH 登录到 10.0.0.15
ssh root@10.0.0.15

# 克隆仓库（需要先在 GitHub 设置 Deploy Key 或使用 PAT）
cd /root
git clone https://YOUR_TOKEN@github.com/pxMan79/ops-relay.git

# 进入项目目录
cd ops-relay

# 配置文件（从模板复制）
cp config.yml.example config.yml
cp .env.example .env

# 编辑配置（填入真实值）
nano config.yml
nano .env

# 一键部署
chmod +x deploy.sh
bash deploy.sh --prod
```

### 方式二：使用 GitHub Actions 自动部署（高级）

创建 `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Server

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to server via SSH
        uses: appleboy/scp-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "."
          target: "/root/ops-relay"
          
      - name: Restart services
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /root/ops-relay
            bash deploy.sh --prod
```

---

## ⚠️ 常见问题解决

### 问题 1: 推送失败 - Authentication failed

**原因**: 未配置认证方式或 Token 过期

**解决**:
```bash
# 使用 SSH
git remote set-url origin git@github.com:pxMan79/ops-relay.git

# 或重新生成 PAT 并更新 URL
git remote set-url origin https://NEW_TOKEN@github.com/pxMan79/ops-relay.git
```

### 问题 2: 文件过大导致推送失败

**原因**: 可能误提交了大文件（如 node_modules, .db 等）

**解决**:
```bash
# 检查大文件
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print $3, $4}' | sort -rn | head -20

# 从历史中移除大文件（谨慎操作！）
git filter-branch --force --index-filter 'git rm -cached --ignore-unmatch PATH_TO_LARGE_FILE' --prune-empty --tag-name-filter cat -- --all
```

### 问题 3: 冲突合并

**原因**: 多设备或历史分支同步时产生冲突

**解决**:
```bash
# 先拉取最新代码
git pull origin main --rebase

# 手动解决冲突（编辑标记为 <<<<<<< 的文件）

# 继续变基
git rebase --continue

# 推送
git push origin main
```

---

## 📊 仓库管理建议

### 分支策略

```
main          ← 默认维护分支
hotfix/*      ← 可选，紧急修复时临时使用
```

### 保护规则设置

进入 GitHub 仓库 Settings → Branches → Add rule:

- Branch name pattern: `main`
- Require a pull request before merging: ✅ 启用
- Require status checks to pass: 可选（添加 CI/CD 后启用）
- Do not allow force pushes: ✅ 启用
- Do not allow deletions: ✅ 启用

### 提交规范

- Commit Message 格式:
  - `✨ feat: 新功能`
  - `🐛 fix: Bug 修复`
  - `📝 docs: 文档更新`
  - `♻️ refactor: 代码重构`
  - `⚡ perf: 性能优化`
  - `🔒 security: 安全修复`

---

## 🎉 完成！

恭喜你！现在你的项目已经：

✅ **Docker 化**: 支持一键容器化部署  
✅ **GitHub 托管**: 版本控制和个人维护  
✅ **脱敏处理**: 敏感信息不会泄露  
✅ **文档完善**: README + 部署指南齐全  

下一步：
1. 🌐 在浏览器打开你的 GitHub 仓库查看
2. 🖥️ 在 10.0.0.15 上克隆并部署
3. 🔐 保持仓库为你个人维护模式

---

**需要帮助?**
- GitHub Docs: https://docs.github.com/
- Git 官方文档: https://git-scm.com/doc
- 本项目 Issues: https://github.com/pxMan79/ops-relay/issues
