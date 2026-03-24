import { clerkMiddleware } from '@clerk/nextjs/server'

// No server-side route protection — client-side Clerk handles redirects.
// The backend validates JWT on every API call, so security is maintained.
export default clerkMiddleware()

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
