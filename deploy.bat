@echo off
chcp 65001 >nul
REM ============================================
REM ops-relay Windows 部署脚本
REM 用法: deploy.bat [dev|prod|stop|logs|status]
REM ============================================

setlocal enabledelayedexpansion

set PROJECT_DIR=%~dp0
set COMPOSE_FILE=docker-compose.yml
set COMPOSE_PROD=docker-compose.prod.yml

if "%1"=="" goto help
if "%1"=="dev" goto dev
if "%1"=="prod" goto prod
if "%1"=="stop" goto stop
if "%1"=="logs" goto logs
if "%1"=="status" goto status
if "%1"=="help" goto help

:help
echo.
echo ============================================
echo   ops-relay 部署管理脚本 (Windows)
echo ============================================
echo.
echo 用法: deploy.bat [选项]
echo.
echo   dev      开发环境部署
echo   prod     生产环境部署
echo   stop     停止所有服务
echo   logs     查看日志
echo   status   查看状态
echo.
goto end

:dev
echo [INFO] 🚀 开始开发环境部署...
cd /d %PROJECT_DIR%
docker compose -f %COMPOSE_FILE% up -d --build
echo.
echo [SUCCESS] ✅ 开发环境部署完成！
echo 访问地址: http://localhost:8081
echo API 文档: http://localhost:8001/docs
goto end

:prod
echo [INFO] 🏭 开始生产环境部署...
cd /d %PROJECT_DIR%
docker compose -f %COMPOSE_PROD% up -d --build
timeout /t 10 >nul
echo [SUCCESS] ✅ 生产环境部署完成！
goto end

:stop
echo [INFO] ⏹️  正在停止所有服务...
cd /d %PROJECT_DIR%
docker compose -f %COMPOSE_FILE% down
if exist %COMPOSE_PROD% docker compose -f %COMPOSE_PROD% down
echo [SUCCESS] ✅ 所有服务已停止
goto end

:logs
echo [INFO] 📋 查看实时日志 (Ctrl+C 退出)...
cd /d %PROJECT_DIR%
if exist %COMPOSE_PROD% (
    docker compose -f %COMPOSE_PROD% logs -f --tail=100
) else (
    docker compose -f %COMPOSE_FILE% logs -f --tail=100
)
goto end

:status
echo [INFO] 📊 服务状态...
cd /d %PROJECT_DIR%
docker compose -f %COMPOSE_FILE% ps
if exist %COMPOSE_PROD% docker compose -f %COMPOSE_PROD% ps
goto end

:end
endlocal
