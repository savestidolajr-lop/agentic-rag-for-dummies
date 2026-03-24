import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0d0d0d]">
      <div className="flex flex-col items-center gap-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-white tracking-tight">Case Agent</h1>
          <p className="text-sm text-[#666] mt-1">AI-powered legal research</p>
        </div>
        <SignIn afterSignInUrl="/chat" afterSignUpUrl="/chat" />
      </div>
    </div>
  )
}
