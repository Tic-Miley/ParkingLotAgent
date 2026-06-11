import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
}

export function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 语音识别
  const {
    isSupported,
    isListening,
    interimText,
    error: speechError,
    startListening,
    stopListening,
    clearError,
  } = useSpeechRecognition({
    onFinalResult: (text: string) => {
      setInput(prev => {
        const trimmed = text.trim();
        if (!trimmed) return prev;
        if (prev && !prev.endsWith(' ') && !prev.endsWith('\n')) {
          return prev + ' ' + trimmed;
        }
        return prev + trimmed;
      });
    },
  });

  // 录音中将实时识别文本叠加到输入框末尾
  const displayValue = isListening ? input + interimText : input;

  useEffect(() => {
    if (textareaRef.current) {
      const el = textareaRef.current;
      el.style.height = 'auto';
      const style = getComputedStyle(el);
      const borderTop = parseFloat(style.borderTopWidth) || 0;
      const borderBottom = parseFloat(style.borderBottomWidth) || 0;
      el.style.height = Math.min(el.scrollHeight + borderTop + borderBottom, 120) + 'px';
    }
  }, [input, interimText]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming || isListening) return;
      handleSend();
    }
  };

  return (
    <div className="border-t border-[var(--color-border)] px-4 py-3 bg-[var(--color-bg)]/95">
      {/* 语音错误提示 */}
      {speechError && (
        <div className="max-w-3xl mx-auto mb-2 px-1">
          <div className="text-xs text-red-400 flex items-center gap-1">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{speechError}</span>
            <button onClick={clearError} className="ml-1 underline hover:text-red-300 transition-colors">
              忽略
            </button>
          </div>
        </div>
      )}

      <div className="max-w-3xl mx-auto flex gap-3 items-end">
        <textarea
          ref={textareaRef}
          value={displayValue}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? '正在聆听...' : '输入您的问题...'}
          rows={1}
          readOnly={isListening}
          disabled={isStreaming}
          className="flex-1 resize-none overflow-y-auto rounded-xl bg-[var(--color-input)] border border-[var(--color-border)]
                     px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)]
                     focus:outline-none focus:border-warm-yellow/50 focus:ring-1 focus:ring-warm-yellow/20
                     disabled:opacity-50 transition-colors chat-textarea"
        />

        {/* 麦克风按钮 — 仅 Chrome/Edge 可见 */}
        {isSupported && (
          <button
            onClick={isListening ? stopListening : startListening}
            disabled={isStreaming}
            className={`shrink-0 w-10 h-10 rounded-full border flex items-center justify-center transition-all
              ${isListening
                ? 'bg-red-500/20 border-red-500/30 text-red-400 animate-pulse'
                : 'bg-[var(--color-input)] border-[var(--color-border)] text-[var(--color-text-tertiary)] hover:text-warm-yellow hover:border-warm-yellow/30'
              }
              disabled:opacity-30 disabled:cursor-not-allowed`}
            title={isListening ? '停止录音' : '语音输入'}
          >
            <MicIcon />
          </button>
        )}

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
            disabled={!input.trim() || isListening}
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

function MicIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
    </svg>
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
