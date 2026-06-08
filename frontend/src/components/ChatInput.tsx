import { useState, useRef, useEffect, KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
}

export function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      const el = textareaRef.current;
      // 重置为 auto 以获取真实 scrollHeight
      el.style.height = 'auto';
      // border-box 下 scrollHeight 不含 border，需补偿
      const style = getComputedStyle(el);
      const borderTop = parseFloat(style.borderTopWidth) || 0;
      const borderBottom = parseFloat(style.borderBottomWidth) || 0;
      el.style.height = Math.min(el.scrollHeight + borderTop + borderBottom, 120) + 'px';
    }
  }, [input]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSend();
    }
  };

  return (
    <div className="border-t border-[var(--color-border)] px-4 py-3 bg-[var(--color-bg)]/95">
      <div className="max-w-3xl mx-auto flex gap-3 items-end">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入您的问题..."
          rows={1}
          disabled={isStreaming}
          className="flex-1 resize-none overflow-y-auto rounded-xl bg-[var(--color-input)] border border-[var(--color-border)]
                     px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)]
                     focus:outline-none focus:border-warm-yellow/50 focus:ring-1 focus:ring-warm-yellow/20
                     disabled:opacity-50 transition-colors chat-textarea"
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="shrink-0 w-10 h-10 rounded-full bg-red-500/20 border border-red-500/30
                       flex items-center justify-center text-red-400 hover:bg-red-500/30 transition-colors"
            title="停止生成"
          >
            <StopIcon />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="shrink-0 w-10 h-10 rounded-full bg-warm-yellow/20 border border-warm-yellow/30
                       flex items-center justify-center text-warm-yellow
                       hover:bg-warm-yellow/30 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="发送"
          >
            <SendIcon />
          </button>
        )}
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <rect x="4" y="4" width="16" height="16" rx="2" />
    </svg>
  );
}
