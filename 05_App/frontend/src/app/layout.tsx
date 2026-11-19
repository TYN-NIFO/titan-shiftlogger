import type { Metadata, Viewport } from "next";
import "./globals.css";
import { appFont, codeFont } from "@/lib/fonts";
import AppShell from "@/components/shell/AppShell";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "Shift Logger",
  description: "Job cards read by AI, checked, reviewed and queried in plain language.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0b2227",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${appFont.variable} ${codeFont.variable}`}>
      <body className="font-sans">
        <ToastProvider>
          <AppShell>{children}</AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
