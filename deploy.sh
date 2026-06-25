#!/bin/bash
# ============================================
# ops-relay 单容器部署脚本（IP+端口直连模式）
# 用法: bash deploy.sh [选项]
#   (默认) / --up    构建并启动 ops-relay 单容器
#   --stop           停止
#   --logs           实时日志
#   --status         容器状态 + 资源占用
#   --help           帮助
# 访问：http://<本机IP>:8001 （不经 NPM）
# ============================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
COMPOSE_FILE="docker-compose.yml"
PROJECT_DIR="${OPS_RELAY_DIR:-$(cd "$(dirname "$0")" && pwd)}"

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

ensure_compose() {
    if [ ! -f "$PROJECT_DIR/$COMPOSE_FILE" ]; then
        log_error "找不到 $PROJECT_DIR/$COMPOSE_FILE"
        log_info "请在项目目录运行，或设 OPS_RELAY_DIR 指向项目路径"
        exit 1
    fi
}

deploy() {
    log_info "🚀 部署 ops-relay 单容器..."
    ensure_compose
    command -v docker >/dev/null 2>&1 || { log_error "未安装 docker"; exit 1; }
    docker compose version >/dev/null 2>&1 || { log_error "未安装 docker compose"; exit 1; }

    [ -f "$PROJECT_DIR/config.yml" ] || cp "$PROJECT_DIR/config.yml.example" "$PROJECT_DIR/config.yml" 2>/dev/null || true

    # 迁移清理：移除旧版 frontend+backend 双容器（已改为单体），避免抢 8001 端口
    log_info "清理旧版双容器（如有）..."
    docker rm -f ops-relay-backend ops-relay-frontend ops-relay-backend-prod ops-relay-frontend-prod 2>/dev/null || true

    cd "$PROJECT_DIR"
    docker compose -f "$COMPOSE_FILE" up -d --build

    log_info "等待健康检查..."
    for i in $(seq 1 20); do
        if curl -sf http://localhost:8001/health >/dev/null 2>&1; then
            log_success "✅ 就绪 (http://$(hostname -I | awk '{print $1}'):8001)"
            break
        fi
        sleep 3
    done

    cat <<EOF

${GREEN}部署完成${NC}
  访问地址 : http://$(hostname -I | awk '{print $1}'):8001
  API 文档 : http://$(hostname -I | awk '{print $1}'):8001/docs
EOF
}

stop_services() {
    ensure_compose
    cd "$PROJECT_DIR" && docker compose -f "$COMPOSE_FILE" down
    log_success "已停止"
}

show_logs() {
    ensure_compose
    cd "$PROJECT_DIR" && docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

show_status() {
    ensure_compose
    cd "$PROJECT_DIR"
    docker compose -f "$COMPOSE_FILE" ps
    echo "----"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | grep -i ops-relay || true
}

case "${1:---up}" in
    --up|--prod|--dev|"") deploy ;;
    --stop) stop_services ;;
    --logs) show_logs ;;
    --status) show_status ;;
    -h|--help)
        echo "ops-relay 单容器部署（IP+端口直连）"
        echo "用法: bash deploy.sh [--up|--stop|--logs|--status]"
        ;;
    *) log_error "未知参数: $1"; exit 1 ;;
esac
