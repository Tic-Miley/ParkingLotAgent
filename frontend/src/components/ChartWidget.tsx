import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { ChartData } from '../types/chat';
import { useTheme } from '../hooks/useTheme';

interface ChartWidgetProps {
  chart: ChartData;
}

// ── 浅色模式配色（新默认）──
const LIGHT_DATA_COLORS = ['#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2'];
const LIGHT_TEXT_PRIMARY = '#2c2c2c';
const LIGHT_TEXT_SECONDARY = '#6b6560';
const LIGHT_BORDER = '#d9d4cc';
const LIGHT_TOOLTIP_BG = 'rgba(255, 255, 255, 0.95)';

// ── 深色模式配色 ──
const DARK_DATA_COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee'];
const DARK_TEXT_PRIMARY = '#e2e8f0';
const DARK_TEXT_SECONDARY = '#94a3b8';
const DARK_BORDER = '#2a2a5a';
const DARK_TOOLTIP_BG = 'rgba(26, 26, 46, 0.95)';

type PlainObject = Record<string, unknown>;

interface AxisPatchArgs {
  axis: PlainObject;
  labelColor: string;
  lineColor: string;
  splitLineColor: string;
}

/** Patch a single axis object with theme-aware colors */
function patchSingleAxis(args: AxisPatchArgs): PlainObject {
  const { axis, labelColor, lineColor, splitLineColor } = args;
  const patched = { ...axis };
  if (patched.axisLabel && typeof patched.axisLabel === 'object') {
    patched.axisLabel = { ...(patched.axisLabel as PlainObject), color: labelColor };
  }
  if (patched.axisLine && typeof patched.axisLine === 'object') {
    const line = patched.axisLine as PlainObject;
    patched.axisLine = {
      ...line,
      lineStyle: { ...(line.lineStyle as PlainObject || {}), color: lineColor },
    };
  }
  // Y-axis splitLine
  if (patched.splitLine && typeof patched.splitLine === 'object') {
    const sl = patched.splitLine as PlainObject;
    patched.splitLine = {
      ...sl,
      lineStyle: { ...(sl.lineStyle as PlainObject || {}), color: splitLineColor },
    };
  }
  return patched;
}

/**
 * 将 LLM 生成的 ECharts option 根据当前主题做完整颜色注入。
 * 无论深色/浅色，始终由前端统一管理所有视觉属性。
 */
function adaptChartOption(option: Record<string, unknown>, theme: 'dark' | 'light'): Record<string, unknown> {
  const dataColors = theme === 'dark' ? DARK_DATA_COLORS : LIGHT_DATA_COLORS;
  const textPrimary = theme === 'dark' ? DARK_TEXT_PRIMARY : LIGHT_TEXT_PRIMARY;
  const textSecondary = theme === 'dark' ? DARK_TEXT_SECONDARY : LIGHT_TEXT_SECONDARY;
  const border = theme === 'dark' ? DARK_BORDER : LIGHT_BORDER;
  const tooltipBg = theme === 'dark' ? DARK_TOOLTIP_BG : LIGHT_TOOLTIP_BG;

  const adapted: PlainObject = { ...option };

  // 1. 数据系列颜色 — 始终注入，覆盖 LLM 可能指定的颜色
  adapted.color = dataColors;

  // 2. Title
  if (adapted.title && typeof adapted.title === 'object') {
    const t = adapted.title as PlainObject;
    adapted.title = { ...t, textStyle: { ...(t.textStyle as PlainObject || {}), color: textPrimary } };
  }

  // 3. Legend
  if (adapted.legend && typeof adapted.legend === 'object') {
    const l = adapted.legend as PlainObject;
    adapted.legend = { ...l, textStyle: { ...(l.textStyle as PlainObject || {}), color: textSecondary } };
  }

  // 4. Tooltip
  if (adapted.tooltip && typeof adapted.tooltip === 'object') {
    const tt = adapted.tooltip as PlainObject;
    adapted.tooltip = {
      ...tt,
      backgroundColor: tooltipBg,
      borderColor: border,
      textStyle: { ...(tt.textStyle as PlainObject || {}), color: textPrimary },
    };
  }

  // 5. xAxis — 支持单对象和数组
  if (adapted.xAxis) {
    const axisArgs = { labelColor: textSecondary, lineColor: border, splitLineColor: border };
    if (Array.isArray(adapted.xAxis)) {
      adapted.xAxis = adapted.xAxis.map(a => patchSingleAxis({ axis: a as PlainObject, ...axisArgs }));
    } else if (typeof adapted.xAxis === 'object') {
      adapted.xAxis = patchSingleAxis({ axis: adapted.xAxis as PlainObject, ...axisArgs });
    }
  }

  // 6. yAxis — 支持单对象和数组
  if (adapted.yAxis) {
    const axisArgs = { labelColor: textSecondary, lineColor: border, splitLineColor: border };
    if (Array.isArray(adapted.yAxis)) {
      adapted.yAxis = adapted.yAxis.map(a => patchSingleAxis({ axis: a as PlainObject, ...axisArgs }));
    } else if (typeof adapted.yAxis === 'object') {
      adapted.yAxis = patchSingleAxis({ axis: adapted.yAxis as PlainObject, ...axisArgs });
    }
  }

  return adapted;
}

export function ChartWidget({ chart }: ChartWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!containerRef.current) return;

    if (!instanceRef.current) {
      instanceRef.current = echarts.init(containerRef.current, undefined, {
        backgroundColor: 'transparent',
      } as any);
    }

    const adaptedOption = adaptChartOption(chart.option, theme);

    const option = {
      ...adaptedOption,
      animationDuration: 800,
    };

    instanceRef.current.setOption(option, true);

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [chart, theme]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  return (
    <div className="mb-4 bg-[var(--color-surface)]/30 border border-[var(--color-border)]/40 rounded-xl p-4 animate-slide-up">
      <div ref={containerRef} style={{ width: '100%', height: '320px' }} />
    </div>
  );
}