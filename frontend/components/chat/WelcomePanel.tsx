'use client'

interface WelcomePanelProps {
  userName: string
  stateFilter: string
  onPrompt: (text: string) => void
}

const SUGGESTIONS = [
  'What are the key deadlines under the security of payment legislation?',
  'Summarise the adjudication process and timeframes.',
  'What constitutes a valid payment claim?',
  'Explain principal contractor obligations for subcontractor payments.',
]

export default function WelcomePanel({ userName, stateFilter, onPrompt }: WelcomePanelProps) {
  const greeting = userName ? `Hello, ${userName}!` : 'Hello!'
  const context = stateFilter && stateFilter !== 'All States' ? stateFilter : null

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 gap-6 text-center">
      <div className="flex flex-col items-center gap-2">
        <div className="text-3xl mb-1">⚖️</div>
        <h1 className="text-xl font-semibold text-[#ececec]">{greeting}</h1>
        <p className="text-sm text-[#555] max-w-xs">
          {context
            ? `Ask me anything about ${context} construction law.`
            : 'Select a state above, then start your research.'}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPrompt(s)}
            className="text-left text-xs text-[#888] bg-[#111] hover:bg-[#1a1a1a]
                       border border-[#1e1e1e] hover:border-[#2d2d2d]
                       rounded-xl px-4 py-3 transition-colors leading-relaxed"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
