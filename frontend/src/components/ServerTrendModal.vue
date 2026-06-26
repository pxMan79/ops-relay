<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from "vue";
import * as echarts from "echarts";
import { fetchHistory } from "../utils/api";

const props = defineProps<{ ip: string }>();
const emit = defineEmits<{ close: [] }>();

const chartEl = ref<HTMLDivElement | null>(null);
const loading = ref(false);
const empty = ref(false);
let chart: echarts.ECharts | null = null;

async function render() {
  loading.value = true;
  empty.value = false;
  try {
    const res: any = await fetchHistory({ ip: props.ip, interval: "1h" });
    const data = res?.data || {};
    const ts: string[] = data.timestamps || [];
    const series: any[] = (data.series || []).filter((s: any) => s.ip === props.ip);
    if (!ts.length || !series.length) {
      empty.value = true;
      return;
    }
    const s = series[0];
    await nextTick();
    if (!chartEl.value) return;
    chart = echarts.init(chartEl.value);
    chart.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      legend: { data: ["CPU", "内存", "磁盘"], textStyle: { color: "#cbd5e1" }, top: 0 },
      grid: { left: 44, right: 20, top: 36, bottom: 56 },
      xAxis: { type: "category", boundaryGap: false, data: ts, axisLabel: { color: "#94a3b8", rotate: 40, fontSize: 10 } },
      yAxis: { type: "value", max: 100, axisLabel: { color: "#94a3b8", formatter: "{value}%" }, splitLine: { lineStyle: { color: "#334155" } } },
      series: [
        { name: "CPU", type: "line", smooth: true, showSymbol: true, data: s.cpu_usage, itemStyle: { color: "#22d3ee" } },
        { name: "内存", type: "line", smooth: true, showSymbol: true, data: s.memory_percent, itemStyle: { color: "#f59e0b" } },
        { name: "磁盘", type: "line", smooth: true, showSymbol: true, data: s.disk_percent, itemStyle: { color: "#ef4444" } },
      ],
    });
  } catch (e) {
    empty.value = true;
  } finally {
    loading.value = false;
  }
}

function onResize() {
  chart?.resize();
}
onMounted(() => {
  render();
  window.addEventListener("resize", onResize);
});
onUnmounted(() => {
  window.removeEventListener("resize", onResize);
  chart?.dispose();
});
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
    @click.self="emit('close')"
  >
    <div class="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-3xl shadow-2xl">
      <div class="flex justify-between items-center mb-3">
        <div>
          <h3 class="text-lg font-bold text-white font-mono">{{ ip }}</h3>
          <p class="text-xs text-slate-400">历史趋势 · CPU / 内存 / 磁盘 使用率</p>
        </div>
        <button
          @click="emit('close')"
          class="text-slate-400 hover:text-white text-2xl leading-none px-2"
          aria-label="关闭"
        >
          ×
        </button>
      </div>
      <div v-if="loading" class="h-72 flex items-center justify-center text-slate-400">加载中...</div>
      <div v-else-if="empty" class="h-72 flex items-center justify-center text-slate-500 text-sm">
        暂无历史数据（数据随每次采集累积，当前点数较少属正常）
      </div>
      <div v-show="!loading && !empty" ref="chartEl" class="h-72"></div>
    </div>
  </div>
</template>
