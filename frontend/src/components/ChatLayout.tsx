import { useChat } from '../hooks/useChat';
import { Header } from './Header';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { QuickQuestions } from './QuickQuestions';

export function ChatLayout() {
  const { messages, isStreaming, sendMessage, stopStreaming } = useChat();

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="flex flex-col h-screen bg-[var(--color-bg)]">
      <Header />
      <MessageList messages={messages} onCopy={handleCopy} />
      {messages.length === 0 && (
        <QuickQuestions onSelect={sendMessage} disabled={isStreaming} />
      )}
      <ChatInput
        onSend={sendMessage}
        onStop={stopStreaming}
        isStreaming={isStreaming}
      />
    </div>
  );
}
