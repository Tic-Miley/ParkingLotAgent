import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message } from '../types/chat';
import { ToolCallCard } from './ToolCallCard';
import { ChartWidget } from './ChartWidget';

interface AssistantMessageProps {
  message: Message;
  onCopy: (text: string) => void;
}

export function AssistantMessage({ message, onCopy }: AssistantMessageProps) {
  return (
    <div className="px-4 sm:px-6 mb-6 group animate-slide-up">
      <div className="max-w-[85%] sm:max-w-[75%]">
        {/* Tool calls */}
        {message.toolCalls.length > 0 && (
          <div className="mb-3">
            {message.toolCalls.map((tc, i) => (
              <ToolCallCard key={`${tc.toolName}-${i}`} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Message content */}
        {message.content && (
          <div className="bg-[var(--color-surface)]/40 border border-[var(--color-border)]/30 rounded-2xl rounded-bl-md px-4 py-3">
            <div className="markdown-body text-sm text-[var(--color-text-primary)]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>

            {/* Streaming indicator */}
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 bg-warm-yellow/60 animate-pulse rounded-sm ml-0.5 align-middle" />
            )}

            {/* Copy button */}
            {!message.isStreaming && message.content && (
              <button
                onClick={() => onCopy(message.content)}
                className="mt-2 text-xs text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] transition-colors
                           opacity-0 group-hover:opacity-100"
              >
                复制
              </button>
            )}
          </div>
        )}

        {/* Empty streaming state */}
        {!message.content && message.isStreaming && (
          <div className="bg-[var(--color-surface)]/40 border border-[var(--color-border)]/30 rounded-2xl rounded-bl-md px-4 py-3">
            <div className="flex gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[var(--color-text-tertiary)] animate-pulse-dot" style={{ animationDelay: '0s' }} />
              <span className="w-2 h-2 rounded-full bg-[var(--color-text-tertiary)] animate-pulse-dot" style={{ animationDelay: '0.2s' }} />
              <span className="w-2 h-2 rounded-full bg-[var(--color-text-tertiary)] animate-pulse-dot" style={{ animationDelay: '0.4s' }} />
            </div>
          </div>
        )}

        {/* Charts */}
        {message.charts.length > 0 && (
          <div className="mt-2">
            {message.charts.map(chart => (
              <ChartWidget key={chart.chartId} chart={chart} />
            ))}
          </div>
        )}

        {/* Stopped indicator */}
        {!message.isStreaming && !message.content && message.toolCalls.length > 0 && (
          <div className="text-xs text-[var(--color-text-tertiary)] mt-1">已中断</div>
        )}
      </div>
    </div>
  );
}
