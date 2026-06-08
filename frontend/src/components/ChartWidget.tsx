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

type PlainObject = Record<string, unknown>;

/** Patch a single axis object (not array) with light-mode colors */
function patchSingleAxis(axis: PlainObject): PlainObject {
  const patched = { ...axis };
  if (patched.axisLabel && typeof patched.axisLabel === 'object') {
    patched.axisLabel = { ...(patched.axisLabel as PlainObject), color: LIGHT_TEXT_SECONDARY };
  }
  if (patched.axisLine && typeof patched.axisLine === 'object') {
    const line = patched.axisLine as PlainObject;
    patched.axisLine = {
      ...line,
      lineStyle: { ...(line.lineStyle as PlainObject || {}), color: LIGHT_BORDER },
    };
  }
  // Y-axis only
  if (patched.splitLine && typeof patched.splitLine === 'object') {
    const sl = patched.splitLine as PlainObject;
    patched.splitLine = {
      ...sl,
      lineStyle: { ...(sl.lineStyle as PlainObject || {}), color: LIGHT_BORDER },
    };
  }
  return patched;
}

function adaptChartOption(option: Record<string, unknown>, theme: 'dark' | 'light'): Record<string, unknown> {
  if (theme === 'dark') return option;

  const adapted: PlainObject = { ...option };

  // Title
  if (adapted.title && typeof adapted.title === 'object') {
    const t = adapted.title as PlainObject;
    adapted.title = { ...t, textStyle: { ...(t.textStyle as PlainObject || {}), color: LIGHT_TEXT_PRIMARY } };
  }

  // Legend
  if (adapted.legend && typeof adapted.legend === 'object') {
    const l = adapted.legend as PlainObject;
    adapted.legend = { ...l, textStyle: { ...(l.textStyle as PlainObject || {}), color: LIGHT_TEXT_SECONDARY } };
  }

  // Tooltip
  if (adapted.tooltip && typeof adapted.tooltip === 'object') {
    const tt = adapted.tooltip as PlainObject;
    adapted.tooltip = {
      ...tt,
      backgroundColor: LIGHT_TOOLTIP_BG,
      borderColor: LIGHT_BORDER,
      textStyle: { ...(tt.textStyle as PlainObject || {}), color: LIGHT_TEXT_PRIMARY },
    };
  }

  // X Axis — handle both single object and array
  if (adapted.xAxis) {
    if (Array.isArray(adapted.xAxis)) {
      adapted.xAxis = adapted.xAxis.map(a => patchSingleAxis(a as PlainObject));
    } else if (typeof adapted.xAxis === 'object') {
      adapted.xAxis = patchSingleAxis(adapted.xAxis as PlainObject);
    }
  }

  // Y Axis — handle both single object and array
  if (adapted.yAxis) {
    if (Array.isArray(adapted.yAxis)) {
      adapted.yAxis = adapted.yAxis.map(a => patchSingleAxis(a as PlainObject));
    } else if (typeof adapted.yAxis === 'object') {
      adapted.yAxis = patchSingleAxis(adapted.yAxis as PlainObject);
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
