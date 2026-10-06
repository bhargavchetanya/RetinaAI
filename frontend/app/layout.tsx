import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import ChatWidget from "@/components/ChatWidget";
import { LangProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "RetinaAI – Explainable DR Screening",
  description: "Explainable AI for diabetic retinopathy screening in rural India",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <AuthProvider>
          <LangProvider>
            <Navbar />
            {children}
            <ChatWidget />
          </LangProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
