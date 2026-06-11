import { useEffect, useRef } from 'react';
import { Message } from '../types/chat';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { EmptyState } from './EmptyState';

interface MessageListProps {
  messages: Message[];
  onCopy: (text: string) => void;
}

export function MessageList({ messages, onCopy }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 用户是否想要自动滚动到底部（用户意图，非被动位置判断）
  const userWantsAutoScrollRef = useRef(true);
  // 是否正在执行程序触发的自动滚动（用于在 scroll 事件中忽略噪声）
  const isAutoScrollingRef = useRef(false);

  // ── 1. wheel 事件：检测用户主动向上滚动意图 ──
  // wheel 事件只能由用户物理输入（鼠标滚轮/触摸板）触发，
  // 不会被 scrollIntoView 触发，因此是区分用户意图的可靠信号。
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      if (e.deltaY < -3) {
        // 用户向上滚动 → 锁定不自动滚动
        userWantsAutoScrollRef.current = false;

        // 如果有正在进行的 smooth 自动滚动，立即中断
        if (isAutoScrollingRef.current) {
          // scrollTo + behavior:'auto' 比 scrollTop=scrollTop 更可靠地中断 smooth 动画
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
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;

      // 自动滚动进行中 → 检测是否到达底部（说明自动滚动完成）
      if (isAutoScrollingRef.current) {
        if (isAtBottom) {
          isAutoScrollingRef.current = false;
        }
        return; // 忽略自动滚动产生的中间 scroll 事件
      }

      // 用户手动滚动到底部 → 解锁自动滚动
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
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });

      // 兜底：600ms 后强制重置 isAutoScrollingRef，
      // 防止因某些浏览器不触发 scrollend/scroll 导致标记永远为 true
      const fallbackTimer = setTimeout(() => {
        isAutoScrollingRef.current = false;
      }, 600);

      return () => clearTimeout(fallbackTimer);
    }
  }, [messages]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  // ── 关键修复：containerRef 必须始终绑定，不能因 empty state 而提前返回 ──
  // 否则挂载时 useEffect([]) 获取不到容器，wheel/scroll 监听器永远不会绑定。
  return (
    <div className="flex-1">
      <div ref={containerRef} className="h-full overflow-y-auto py-4">
        {messages.length === 0 ? (
          <div className="max-w-3xl mx-auto h-full flex items-center justify-center">
            <EmptyState />
          </div>
        ) : (
          <div className="max-w-[54rem] mx-auto">
            {messages.map(msg =>
              msg.role === 'user' ? (
                <UserMessage key={msg.id} message={msg} />
              ) : (
                <AssistantMessage key={msg.id} message={msg} onCopy={handleCopy} />
              )
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  );
}
