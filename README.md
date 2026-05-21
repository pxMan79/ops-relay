# ops-relay

🚀 **基于 Ansible + FastAPI + Vue 3 的内网服务器监控平台**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-4FC08D.svg)](https://vuejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## ✨ 核心特性

- 🔧 **配置驱动**: YAML 外置配置，支持热加载
- 🌐 **RESTful API**: 6 个标准化接口，易于集成
- 📊 **Web Dashboard**: 暗色科技风监控大屏
- 💾 **数据持久化**: SQLite 历史记录存储
- 🐳 **Docker 化**: 一键部署，开箱即用
- ⚠️ **双阶梯告警**: 内存/磁盘/CPU 智能预警
- 🤖 **钉钉集成**: 预留 Webhook 接口

---

## 🏗️ 架构概览

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   前端 (Vue 3)   │────▶│  Nginx 反向代理    │────▶│ 后端 API    │
│   端口: 80      │     │                  │     │ 端口: 8000  │
└─────────────────┘     └──────────────────┘     └──────┬──────┘
                                                         │
                        ┌────────────────────────────────┘
                        │
                   ┌────▼────┐
                   │ SQLite  │
                   │ 数据库   │
                   └─────────┘
```

---

## 🚀 快速开始（Docker 部署）

### 方式一：一键部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/ops-relay.git
cd ops-relay

# 2. 配置文件（重要！）
cp config.yml.example config.yml
cp .env.example .env
# 编辑 config.yml 和 .env，填入真实配置

# 3. 一键启动
chmod +x deploy.sh
bash deploy.sh --dev    # 开发环境
# 或
bash deploy.sh --prod   # 生产环境

# 4. 访问服务
# 前端: http://YOUR_SERVER_IP
# API 文档: http://YOUR_SERVER_IP:8000/docs
```

### 方式二：手动 Docker Compose

```bash
# 开发环境
docker compose up -d --build

# 生产环境（带资源限制和日志收集）
docker compose -f docker-compose.prod.yml up -d --build

# 查看日志
docker compose logs -f backend

# 停止服务
docker compose down
```

---

## 📦 本地开发

### 前置要求

- Python 3.9+
- Node.js 18+
- Docker & Docker Compose（可选）
- Ansible（被监控机需安装）

### 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

---

## 📡 API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/api/servers` | 获取所有服务器状态 |
| `GET` | `/api/servers/{ip}` | 获取单台服务器详情 |
| `POST` | `/api/collect` | 手动触发采集 |
| `GET` | `/api/history` | 查询历史记录 |
| `GET` | `/health` | 健康检查 |

**完整 API 文档**: 启动后访问 `http://localhost:8000/docs` (Swagger UI)

---

## ⚙️ 配置说明

### 核心配置文件 (`config.yml`)

```yaml
servers:
  groups:
    all_linux:
      - 10.0.0.168
      - 10.0.0.199

alert_thresholds:
  memory:
    warning: 80
    critical: 90

dingtalk:
  enabled: false
  webhook_url: "YOUR_WEBHOOK_URL"
```

完整示例见 [config.yml.example](config.yml.example)

### 环境变量 (`.env`)

```bash
API_TOKEN=YOUR_SECURE_TOKEN
JWT_SECRET=YOUR_RANDOM_SECRET
DINGTALK_WEBHOOK_URL=YOUR_DINGTALK_TOKEN
```

完整模板见 [.env.example](.env.example)

---

## 🐳 Docker 详细说明

### 镜像架构

```
ops-relay/
├── Dockerfile.backend       # 后端镜像 (Python 3.11)
├── Dockerfile.frontend      # 前端镜像 (Node 构建 + Nginx)
├── docker-compose.yml       # 开发环境编排
├── docker-compose.prod.yml  # 生产环境编排（含资源限制）
└── nginx.conf               # Nginx 反向代理配置
```

### 卷挂载说明

| 宿主机路径 | 容器路径 | 用途 |
|-----------|---------|------|
| `./config.yml` | `/app/config.yml` | 配置文件（热更新） |
| `./data/db` | `/app/data` | SQLite 数据库持久化 |
| `~/.ssh` | `/root/.ssh` | SSH 密钥（Ansible 连接） |

### 端口映射

| 服务 | 容器端口 | 宿主机端口 | 说明 |
|------|---------|-----------|------|
| Frontend (Nginx) | 80 | 80 | Web Dashboard |
| Backend (FastAPI) | 8000 | 8000 | REST API |

---

## 🔒 安全最佳实践

⚠️ **生产环境必读**：

1. ✅ **修改默认密码**
   ```bash
   # 编辑 .env 文件
   JWT_SECRET=$(openssl rand -hex 32)
   API_TOKEN=$(openssl rand -hex 16)
   ```

2. ✅ **限制 CORS 来源**
   ```yaml
   # config.yml
   api:
     cors_origins:
       - "https://your-domain.com"
   ```

3. ✅ **启用 HTTPS**
   ```bash
   # 推荐 Nginx 反向代理 + Let's Encrypt SSL
   certbot --nginx -d your-domain.com
   ```

4. ✅ **配置文件权限**
   ```bash
   chmod 600 config.yml .env
   ```

5. ✅ **定期清理日志**
   ```bash
   # Docker 日志已在 docker-compose.prod.yml 中限制大小
   # 手动清理: docker system prune -f
   ```

---

## 📂 项目结构

```
ops-relay/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口
│   ├── config.py               # 配置加载器
│   ├── models.py               # Pydantic 模型
│   ├── routers/                # API 路由
│   │   ├── servers.py          # 服务器接口
│   │   ├── collect.py          # 采集接口
│   │   └── history.py          # 历史接口
│   ├── services/               # 业务逻辑
│   │   └── collector.py        # 数据采集引擎
│   ├── schemas/models.py       # ORM 模型
│   └── requirements.txt
│
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── views/Dashboard.vue # 监控主页
│   │   ├── components/         # 组件
│   │   ├── types/              # 类型定义
│   │   └── utils/api.ts        # API 封装
│   └── package.json
│
├── Dockerfile.backend          # 后端镜像
├── Dockerfile.frontend         # 前端镜像
├── docker-compose.yml          # 开发编排
├── docker-compose.prod.yml     # 生产编排
├── deploy.sh                   # Linux 部署脚本
├── deploy.bat                  # Windows 部署脚本
├── nginx.conf                  # Nginx 配置
├── config.yml.example          # 配置模板
├── .env.example                # 环境变量模板
├── .gitignore                  # Git 忽略规则
└── README.md                   # 本文档
```

---

## 🔄 更新部署

```bash
cd ops-relay

# 拉取最新代码
git pull origin main

# 重新构建并启动
docker compose up -d --build

# 清理旧镜像（可选）
docker image prune -f
```

---

## 🐛 故障排查

### 问题：容器启动失败

```bash
# 查看详细日志
docker compose logs backend

# 常见原因：
# 1. config.yml 格式错误 → 使用在线 YAML 验证器检查
# 2. 端口占用 → lsof -i :8000 或 netstat -tlnp | grep 8000
# 3. 权限问题 → chmod +x deploy.sh
```

### 问题：Ansible 无法连接

```bash
# 进入容器调试
docker exec -it ops-relay-backend bash

# 测试 SSH 连接
ssh root@10.0.0.168 "hostname"

# 检查密钥权限
ls -la ~/.ssh/id_rsa  # 应该是 600
```

### 问题：前端无法连接后端

```bash
# 检查网络连通性
docker exec ops-relay-frontend curl http://backend:8000/health

# 检查 Nginx 配置
docker exec ops-relay-frontend cat /etc/nginx/conf.d/default.conf
```

---

## 📈 性能优化建议

1. **数据库优化**
   - 定期清理历史数据（`retention_days: 30`）
   - 监控 SQLite 文件大小（建议 < 100MB）

2. **资源限制**
   - 生产环境使用 `docker-compose.prod.yml`（已设置 CPU/内存限制）

3. **缓存策略**
   - Nginx 已配置静态资源长期缓存
   - 可选：接入 Redis 缓存热点查询

4. **监控扩展**
   - 当服务器 >50 台时，考虑迁移到 Prometheus + Grafana

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

## 👥 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Tailwind CSS](https://tailwindcss.com/) - 实用优先的 CSS 框架
- [Lucide Icons](https://lucide.dev/) - 美观的图标库
- [Ansible](https://www.ansible.com/) - 自动化运维工具

---

## 📞 支持

- 📖 [完整文档](docs/)
- 🐛 [Issue 反馈](https://github.com/YOUR_USERNAME/ops-relay/issues)
- 💬 [讨论区](https://github.com/YOUR_USERNAME/ops-relay/discussions)

---

<p align="center">
  Made with ❤️ by Ops Team
</p>
