import { ThemeToggle } from './ThemeToggle';

export function Header() {
  return (
    <header className="flex items-center gap-3 px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 backdrop-blur-sm sticky top-0 z-10">
      <span className="text-2xl">🅿️</span>
      <div className="flex-1">
        <h1 className="text-lg font-semibold text-[var(--color-text-primary)] tracking-wide">停车场 AI 助手</h1>
        <p className="text-xs text-[var(--color-text-tertiary)]">Demo Parking Lot · 智能数据分析</p>
      </div>
      <ThemeToggle />
    </header>
  );
}
