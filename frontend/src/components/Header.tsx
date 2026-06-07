export function Header() {
  return (
    <header className="flex items-center gap-3 px-6 py-4 border-b border-gray-800 bg-surface-dark/80 backdrop-blur-sm sticky top-0 z-10">
      <span className="text-2xl">🅿️</span>
      <div>
        <h1 className="text-lg font-semibold text-white tracking-wide">停车场 AI 助手</h1>
        <p className="text-xs text-gray-500">Demo Parking Lot · 智能数据分析</p>
      </div>
    </header>
  );
}
