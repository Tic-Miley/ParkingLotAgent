import { useState } from 'react';
import { ToolCallEvent } from '../types/chat';

interface ToolCallCardProps {
  toolCall: ToolCallEvent;
}

const TOOL_LABELS: Record<string, string> = {
  get_current_vacancy: '查询空余车位',
  get_nev_ratio: '查询新能源车占比',
  get_trend: '查询停车趋势',
  get_floor_status: '查询楼层状态',
  get_hourly_distribution: '查询时段分布',
  get_vehicle_detail: '查询车辆详情',
  get_summary_stats: '查询汇总统计',
  sql_query: '执行数据查询',
  render_chart: '生成统计图表',
};

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const label = TOOL_LABELS[toolCall.toolName] || toolCall.toolName;
  const isRunning = toolCall.status === 'running';
  const isError = toolCall.status === 'error';

  return (
    <div
      className={`mb-2 text-xs rounded-lg border overflow-hidden transition-all duration-200 animate-slide-up
        ${isError ? 'border-red-500/30 bg-red-500/5' : 'border-[var(--color-border)]/50 bg-[var(--color-surface)]/40'}`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--color-surface-hover)] transition-colors"
      >
        {/* Status icon */}
        {isRunning ? (
          <span className="w-4 h-4 flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse-dot" />
          </span>
        ) : isError ? (
          <span className="text-red-400">✕</span>
        ) : (
          <span className="text-green-400">✓</span>
        )}

        <span className={`flex-1 ${isError ? 'text-red-300' : 'text-[var(--color-text-secondary)]'}`}>
          {isRunning ? `正在${label}...` : isError ? `${label}失败` : `${label}完成`}
        </span>

        {(toolCall.resultPreview || toolCall.error) && (
          <span className="text-[var(--color-text-tertiary)]">
            <Chevron expanded={expanded} />
          </span>
        )}
      </button>

      {expanded && (
        <div className="px-3 py-2 border-t border-[var(--color-border)]/30 bg-[var(--color-surface-code)] font-mono text-xs text-[var(--color-text-secondary)]">
          {toolCall.error ? (
            <div className="text-red-400">{toolCall.error}</div>
          ) : toolCall.resultPreview ? (
            <pre className="whitespace-pre-wrap break-all">
              {typeof toolCall.resultPreview === 'string'
                ? toolCall.resultPreview
                : JSON.stringify(toolCall.resultPreview, null, 2)}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
}

function Chevron({ expanded }: { expanded: boolean }) {
  return (
    <svg
      width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
