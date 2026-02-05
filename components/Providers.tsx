"use client"

import { ToastProvider } from '@/components/Toast'

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <ToastProvider>
            {children}
        </ToastProvider>
    )
}
