import { useState, useRef, useCallback } from 'react';
import { Message, ToolCallEvent, ChartData, generateId } from '../types/chat';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: text,
      toolCalls: [],
      charts: [],
      timestamp: Date.now(),
      isStreaming: false,
    };

    const assistantMsg: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      toolCalls: [],
      charts: [],
      timestamp: Date.now(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              handleSSEEvent(currentEvent, data);
            } catch {
              // ignore parse errors
            }
            currentEvent = '';
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        // user stopped
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsg.id
              ? { ...m, isStreaming: false }
              : m
          )
        );
      } else {
        console.error('Chat error:', err);
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsg.id
              ? { ...m, isStreaming: false, content: m.content || '抱歉，请求失败，请稍后重试。' }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }

    function handleSSEEvent(event: string, data: Record<string, unknown>) {
      setMessages(prev =>
        prev.map(m => {
          if (m.id !== assistantMsg.id) return m;

          switch (event) {
            case 'tool_call': {
              const toolCall: ToolCallEvent = {
                toolName: data.tool_name as string,
                status: data.status as ToolCallEvent['status'],
                arguments: data.arguments as Record<string, unknown> | undefined,
                resultPreview: data.result_preview as string | undefined,
                error: data.error as string | undefined,
              };
              // Replace or append tool call
              const existingIdx = m.toolCalls.findIndex(
                tc => tc.toolName === toolCall.toolName &&
                  (tc.status === 'running' || tc.status === toolCall.status)
              );
              const newToolCalls = [...m.toolCalls];
              if (existingIdx >= 0 && toolCall.status !== 'running') {
                newToolCalls[existingIdx] = toolCall;
              } else if (existingIdx < 0) {
                newToolCalls.push(toolCall);
              }
              return { ...m, toolCalls: newToolCalls };
            }

            case 'text': {
              const token = data.token as string;
              return { ...m, content: m.content + token };
            }

            case 'chart': {
              const chart: ChartData = {
                chartId: data.chart_id as string,
                chartType: data.chart_type as ChartData['chartType'],
                option: data.option as Record<string, unknown>,
              };
              return { ...m, charts: [...m.charts, chart] };
            }

            case 'done':
              return { ...m, isStreaming: false };

            case 'error':
              return {
                ...m,
                isStreaming: false,
                content: m.content || (data.message as string) || '发生错误',
              };

            default:
              return m;
          }
        })
      );
    }
  }, [isStreaming]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { messages, isStreaming, sendMessage, stopStreaming };
}
