<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { Activity, Cpu, HardDrive, AlertTriangle, RefreshCw, Download } from "lucide-vue-next";
import ServerCard from "../components/ServerCard.vue";
import { fetchServers, triggerCollect } from "../utils/api";
import type { ServerListResponse } from "../types/server";

const servers = ref<any[]>([]);
const meta = ref({ total: 0, online: 0, alert_count: 0 });
const loading = ref(false);
const collecting = ref(false);
const lastUpdate = ref<Date | null>(null);
let refreshTimer: ReturnType<typeof setInterval> | null = null;

// 加载服务器数据
async function loadServers() {
  loading.value = true;
  try {
    const response: ServerListResponse = await fetchServers();
    servers.value = response.data || [];
    meta.value = response.meta || { total: 0, online: 0, alert_count: 0 };
    lastUpdate.value = new Date();
  } catch (error) {
    console.error("加载服务器数据失败:", error);
  } finally {
    loading.value = false;
  }
}

// 手动触发数据采集
async function handleCollect() {
  collecting.value = true;
  try {
    await triggerCollect();
    // 等待2秒后重新加载数据
    setTimeout(() => {
      loadServers();
    }, 2000);
  } catch (error) {
    console.error("触发采集失败:", error);
  } finally {
    collecting.value = false;
  }
}

// 刷新数据
function handleRefresh() {
  loadServers();
}

// 自动刷新（每5分钟）
onMounted(() => {
  loadServers();
  refreshTimer = setInterval(loadServers, 5 * 60 * 1000);
});

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }
});
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
    <!-- 顶部导航栏 -->
    <header class="bg-slate-900/50 backdrop-blur-md border-b border-slate-700/50 sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <Activity class="w-8 h-8 text-cyan-400" />
            <div>
              <h1 class="text-xl font-bold tracking-tight">服务器监控系统</h1>
              <p class="text-xs text-slate-400">Server Monitoring Dashboard</p>
            </div>
          </div>

          <div class="flex items-center space-x-3">
            <!-- 最后更新时间 -->
            <div v-if="lastUpdate" class="text-xs text-slate-400 mr-4">
              最后更新: {{ lastUpdate.toLocaleTimeString() }}
            </div>

            <!-- 操作按钮组 -->
            <button
              @click="handleRefresh"
              :disabled="loading"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 disabled:opacity-50"
            >
              <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
              <span>刷新</span>
            </button>

            <button
              @click="handleCollect"
              :disabled="collecting"
              class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 disabled:opacity-50"
            >
              <Activity :size="16" :class="{ 'animate-pulse': collecting }" />
              <span>{{ collecting ? '采集中...' : '立即采集' }}</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="max-w-7xl mx-auto px-6 py-8">
      <!-- 统计卡片区 -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <!-- 总服务器数 -->
        <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 backdrop-blur-sm">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400 mb-1">总服务器</p>
              <p class="text-3xl font-bold font-mono text-white">{{ meta.total }}</p>
            </div>
            <div class="w-12 h-12 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <Activity class="w-6 h-6 text-blue-400" />
            </div>
          </div>
        </div>

        <!-- 在线数量 -->
        <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 backdrop-blur-sm">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400 mb-1">在线</p>
              <p class="text-3xl font-bold font-mono text-emerald-400">{{ meta.online }}</p>
            </div>
            <div class="w-12 h-12 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <Activity class="w-6 h-6 text-emerald-400" />
            </div>
          </div>
        </div>

        <!-- 告警数量 -->
        <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 backdrop-blur-sm">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400 mb-1">告警</p>
              <p class="text-3xl font-bold font-mono text-amber-400">{{ meta.alert_count }}</p>
            </div>
            <div class="w-12 h-12 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <AlertTriangle class="w-6 h-6 text-amber-400" />
            </div>
          </div>
        </div>

        <!-- 平均CPU使用率 -->
        <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 backdrop-blur-sm">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400 mb-1">平均 CPU</p>
              <p class="text-3xl font-bold font-mono text-cyan-400">
                {{
                  servers.filter((s) => s.collection_status === "success").length > 0
                    ? (
                        servers
                          .filter((s) => s.collection_status === "success")
                          .reduce((sum, s) => sum + s.cpu_usage, 0) /
                        servers.filter((s) => s.collection_status === "success").length
                      ).toFixed(1)
                    : 0
                }}%
              </p>
            </div>
            <div class="w-12 h-12 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Cpu class="w-6 h-6 text-cyan-400" />
            </div>
          </div>
        </div>
      </div>

      <!-- 服务器卡片列表 -->
      <div class="mb-6">
        <h2 class="text-lg font-semibold text-slate-200 mb-4 flex items-center space-x-2">
          <HardDrive class="w-5 h-5" />
          <span>服务器状态</span>
          <span class="text-sm font-normal text-slate-400">({{ servers.length }} 台)</span>
        </h2>

        <!-- 加载状态 -->
        <div v-if="loading && servers.length === 0" class="flex items-center justify-center py-20">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
          <span class="ml-3 text-slate-400">加载中...</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading && servers.length === 0" class="text-center py-20">
          <Activity class="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <p class="text-slate-400 text-lg">暂无服务器数据</p>
          <p class="text-slate-500 text-sm mt-2">点击「立即采集」按钮开始收集数据</p>
        </div>

        <!-- 服务器卡片网格 -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <ServerCard
            v-for="server in servers"
            :key="server.id"
            :server="server"
          />
        </div>
      </div>
    </main>

    <!-- 页脚 -->
    <footer class="border-t border-slate-700/50 mt-12 py-6">
      <div class="max-w-7xl mx-auto px-6 text-center text-sm text-slate-500">
        <p>© 2026 服务器监控系统 · Powered by FastAPI + Vue 3</p>
      </div>
    </footer>
  </div>
</template>
