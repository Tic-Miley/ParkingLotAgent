import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { ChartData } from '../types/chat';
import { useTheme } from '../hooks/useTheme';

interface ChartWidgetProps {
  chart: ChartData;
}

const DARK_TEXT_PRIMARY = '#e2e8f0';
const DARK_TEXT_SECONDARY = '#94a3b8';
const DARK_BORDER = '#2a2a5a';
const DARK_TOOLTIP_BG = 'rgba(26, 26, 46, 0.95)';

const LIGHT_TEXT_PRIMARY = '#2c2c2c';
const LIGHT_TEXT_SECONDARY = '#6b6560';
const LIGHT_BORDER = '#d9d4cc';
const LIGHT_TOOLTIP_BG = 'rgba(255, 255, 255, 0.95)';

function adaptChartOption(option: Record<string, unknown>, theme: 'dark' | 'light'): Record<string, unknown> {
  if (theme === 'dark') return option;

  const isLight = theme === 'light';
  const adapted: Record<string, unknown> = { ...option };

  // Helper to safely patch nested objects
  const patch = (obj: Record<string, unknown>, key: string, patcher: (v: Record<string, unknown>) => void) => {
    if (obj[key] && typeof obj[key] === 'object') {
      const copy = { ...(obj[key] as Record<string, unknown>) };
      patcher(copy);
      adapted[key] = copy;
    }
  };

  // Title
  patch(adapted, 'title', v => {
    const ts = { ...(v.textStyle as Record<string, unknown> || {}), color: LIGHT_TEXT_PRIMARY };
    adapted.title = { ...(adapted.title as Record<string, unknown> || {}), textStyle: ts };
  });

  // Legend
  patch(adapted, 'legend', v => {
    const ts = { ...(v.textStyle as Record<string, unknown> || {}), color: LIGHT_TEXT_SECONDARY };
    adapted.legend = { ...(adapted.legend as Record<string, unknown> || {}), textStyle: ts };
  });

  // Tooltip
  patch(adapted, 'tooltip', v => {
    const ts = { ...(v.textStyle as Record<string, unknown> || {}), color: LIGHT_TEXT_PRIMARY };
    adapted.tooltip = {
      ...(adapted.tooltip as Record<string, unknown> || {}),
      backgroundColor: LIGHT_TOOLTIP_BG,
      borderColor: LIGHT_BORDER,
      textStyle: ts,
    };
  });

  // X Axis
  if (adapted.xAxis && typeof adapted.xAxis === 'object') {
    const xAxis = { ...(adapted.xAxis as Record<string, unknown>) };
    if (xAxis.axisLabel && typeof xAxis.axisLabel === 'object') {
      xAxis.axisLabel = { ...(xAxis.axisLabel as Record<string, unknown>), color: LIGHT_TEXT_SECONDARY };
    }
    if (xAxis.axisLine && typeof xAxis.axisLine === 'object') {
      xAxis.axisLine = {
        ...(xAxis.axisLine as Record<string, unknown>),
        lineStyle: { ...((xAxis.axisLine as Record<string, unknown>).lineStyle as Record<string, unknown> || {}), color: LIGHT_BORDER },
      };
    }
    adapted.xAxis = xAxis;
  }

  // Y Axis
  if (adapted.yAxis && typeof adapted.yAxis === 'object') {
    const yAxis = { ...(adapted.yAxis as Record<string, unknown>) };
    if (yAxis.axisLabel && typeof yAxis.axisLabel === 'object') {
      yAxis.axisLabel = { ...(yAxis.axisLabel as Record<string, unknown>), color: LIGHT_TEXT_SECONDARY };
    }
    if (yAxis.splitLine && typeof yAxis.splitLine === 'object') {
      yAxis.splitLine = {
        ...(yAxis.splitLine as Record<string, unknown>),
        lineStyle: { ...((yAxis.splitLine as Record<string, unknown>).lineStyle as Record<string, unknown> || {}), color: LIGHT_BORDER },
      };
    }
    adapted.yAxis = yAxis;
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
