#!/bin/bash
# ============================================
# ops-relay 一键部署脚本 (10.0.0.15)
# 用法: bash deploy.sh [选项]
#   选项:
#     --dev     开发环境部署（带热重载）
#     --prod    生产环境部署（优化配置）
#     --stop    停止所有服务
#     --logs    查看日志
#     --status  查看服务状态
# ============================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="/root/ops-relay"
COMPOSE_FILE="docker-compose.yml"
COMPOSE_PROD="docker-compose.prod.yml"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "检查前置条件..."
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装！请先安装 Docker"
        exit 1
    fi
    
    # 检查 Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装！"
        exit 1
    fi
    
    # 检查项目目录
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "项目目录不存在: $PROJECT_DIR"
        log_info "请先克隆仓库: git clone https://github.com/YOUR_USERNAME/ops-relay.git $PROJECT_DIR"
        exit 1
    fi
    
    # 检查配置文件
    if [ ! -f "$PROJECT_DIR/config.yml" ]; then
        log_warn "config.yml 不存在，使用模板创建..."
        cp "$PROJECT_DIR/config.yml.example" "$PROJECT_DIR/config.yml"
        log_warn "⚠️  请编辑 config.yml 填入真实配置！"
    fi
    
    # 检查 .env 文件
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_warn ".env 不存在，使用模板创建..."
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        log_warn "⚠️  请编辑 .env 填入敏感信息！"
    fi
    
    # 检查 SSH 密钥（Ansible 需要）
    if [ ! -f ~/.ssh/id_rsa ]; then
        log_warn "SSH 密钥不存在，Ansible 可能无法连接远程服务器"
    fi
    
    log_success "前置条件检查通过 ✓"
}

deploy_dev() {
    log_info "🚀 开始开发环境部署..."
    
    cd "$PROJECT_DIR"
    
    # 构建并启动（开发模式）
    docker compose -f "$COMPOSE_FILE" up -d --build
    
    log_success "✅ 开发环境部署完成！"
    echo ""
    echo -e "访问地址:"
    echo -e "  ${GREEN}前端 Dashboard${NC}: http://$(hostname -I | awk '{print $1}')"
    echo -e "  ${GREEN}后端 API 文档${NC}: http://$(hostname -I | awk '{print $1}'):8000/docs"
    echo ""
    echo -e "${YELLOW}提示: 使用 'bash deploy.sh --logs' 查看实时日志${NC}"
}

deploy_prod() {
    log_info "🏭 开始生产环境部署..."
    
    cd "$PROJECT_DIR"
    
    # 使用生产环境 compose 文件
    docker compose -f "$COMPOSE_PROD" up -d --build
    
    # 等待健康检查通过
    log_info "等待服务启动..."
    sleep 10
    
    # 验证服务状态
    if docker compose -f "$COMPOSE_PROD" ps | grep -q "running"; then
        log_success "✅ 生产环境部署完成！"
        echo ""
        echo -e "访问地址:"
        echo -e "  ${GREEN}前端 Dashboard${NC}: http://$(hostname -I | awk '{print $1}')"
        echo -e "  ${GREEN}后端 API${NC}: http://$(hostname -I | awk '{print $1}'):8000"
        echo ""
        log_info "建议配置 Nginx 反向代理 + SSL 证书"
    else
        log_error "❌ 部分服务启动失败，请查看日志: bash deploy.sh --logs"
        exit 1
    fi
}

stop_services() {
    log_info "⏹️  正在停止所有服务..."
    
    cd "$PROJECT_DIR"
    
    # 停止并清理容器
    if [ -f "$COMPOSE_PROD" ]; then
        docker compose -f "$COMPOSE_PROD" down 2>/dev/null || true
    fi
    docker compose -f "$COMPOSE_FILE" down
    
    log_success "✅ 所有服务已停止"
}

show_logs() {
    log_info "📋 查看实时日志 (Ctrl+C 退出)..."
    
    cd "$PROJECT_DIR"
    
    # 优先显示生产环境日志
    if [ -f "$COMPOSE_PROD" ] && docker compose -f "$COMPOSE_PROD" ps --status running | grep -q .; then
        docker compose -f "$COMPOSE_PROD" logs -f --tail=100
    else
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100
    fi
}

show_status() {
    log_info "📊 服务状态概览..."
    
    cd "$PROJECT_DIR"
    
    echo ""
    echo "=========================================="
    echo "  ops-relay 服务状态"
    echo "=========================================="
    
    if [ -f "$COMPOSE_PROD" ] && docker compose -f "$COMPOSE_PROD" ps --format table 2>/dev/null | grep -q .; then
        docker compose -f "$COMPOSE_PROD" ps
    elif docker compose -f "$COMPOSE_FILE" ps --format table | grep -q .; then
        docker compose -f "$COMPOSE_FILE" ps
    else
        log_warn "没有运行中的容器"
    fi
    
    echo ""
    echo "=========================================="
    echo "  系统资源使用"
    echo "=========================================="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
}

# 主逻辑
case "$1" in
    --dev)
        check_prerequisites
        deploy_dev
        ;;
    --prod)
        check_prerequisites
        deploy_prod
        ;;
    --stop)
        stop_services
        ;;
    --logs)
        show_logs
        ;;
    --status)
        show_status
        ;;
    --help|-h|"")
        echo ""
        echo -e "${BLUE}ops-relay 部署管理脚本${NC}"
        echo ""
        echo "用法: bash deploy.sh [选项]"
        echo ""
        echo "选项:"
        echo "  --dev      开发环境部署（默认）"
        echo "  --prod     生产环境部署（优化+资源限制）"
        echo "  --stop     停止所有服务"
        echo "  --logs     查看实时日志"
        echo "  --status   查看服务状态和资源使用"
        echo "  --help     显示帮助信息"
        echo ""
        echo "示例:"
        echo "  bash deploy.sh --dev       # 开发部署"
        echo "  bash deploy.sh --prod      # 生产部署"
        echo "  bash deploy.sh --logs      # 查看日志"
        echo "  bash deploy.sh --status    # 查看状态"
        ;;
    *)
        log_error "未知参数: $1"
        echo "使用 'bash deploy.sh --help' 查看帮助"
        exit 1
        ;;
esac
