import { useEffect, useRef } from 'react';
import { useChat } from '../hooks/useChat';
import { Header } from './Header';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { QuickQuestions } from './QuickQuestions';

export function ChatLayout() {
  const { messages, isStreaming, sendMessage, stopStreaming } = useChat();

  // ── 滚动容器与底部锚点 ──
  const scrollRef = useRef<HTMLDivElement>(null);

  // 用户是否想要自动滚动到底部（用户意图，非被动位置判断）
  const userWantsAutoScrollRef = useRef(true);
  // 是否正在执行程序触发的自动滚动
  const isAutoScrollingRef = useRef(false);

  // ── 1. wheel 事件：检测用户主动向上滚动意图 ──
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      if (e.deltaY < -3) {
        userWantsAutoScrollRef.current = false;
        if (isAutoScrollingRef.current) {
          container.scrollTo({ top: container.scrollTop, behavior: 'auto' });
          isAutoScrollingRef.current = false;
        }
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: true });
    return () => container.removeEventListener('wheel', handleWheel);
  }, []);

  // ── 2. scroll 事件：检测用户是否回到底部（解锁自动滚动）──
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;

      if (isAutoScrollingRef.current) {
        if (isAtBottom) {
          isAutoScrollingRef.current = false;
        }
        return;
      }

      if (isAtBottom) {
        userWantsAutoScrollRef.current = true;
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  // ── 3. 自动滚动到底部 ──
  useEffect(() => {
    if (userWantsAutoScrollRef.current && messages.length > 0) {
      isAutoScrollingRef.current = true;
      const container = scrollRef.current;
      if (container) {
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
      }

      const fallbackTimer = setTimeout(() => {
        isAutoScrollingRef.current = false;
      }, 600);

      return () => clearTimeout(fallbackTimer);
    }
  }, [messages]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div ref={scrollRef} className="flex flex-col h-screen overflow-y-auto bg-[var(--color-bg)]">
      <Header />
      <div className="flex-1 flex flex-col">
        <div className="flex-1">
          <MessageList messages={messages} onCopy={handleCopy} />
        </div>
        {messages.length === 0 && (
          <QuickQuestions onSelect={sendMessage} disabled={isStreaming} />
        )}
      </div>
      <ChatInput
        onSend={sendMessage}
        onStop={stopStreaming}
        isStreaming={isStreaming}
      />
    </div>
  );
}