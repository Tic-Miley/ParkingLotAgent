interface QuickQuestionsProps {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

const QUICK_QUESTIONS = [
  { label: '还剩多少车位？', icon: '🅿️' },
  { label: '新能源车占比？', icon: '🔋' },
  { label: '最近30天趋势？', icon: '📈' },
];

export function QuickQuestions({ onSelect, disabled }: QuickQuestionsProps) {
  return (
    <div className="flex flex-wrap gap-2 px-6 py-3 justify-center">
      {QUICK_QUESTIONS.map(q => (
        <button
          key={q.label}
          onClick={() => onSelect(q.label)}
          disabled={disabled}
          className="flex items-center gap-1.5 px-4 py-2 rounded-full text-sm
                     bg-[var(--color-surface)] border border-[var(--color-border)]/50 text-[var(--color-text-secondary)]
                     hover:border-warm-yellow/40 hover:text-warm-yellow
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all duration-200"
        >
          <span>{q.icon}</span>
          <span>{q.label}</span>
        </button>
      ))}
    </div>
  );
}
