import type { Metadata } from "next";
import "./globals.css";
import { AuthInitializer } from "@/components/AuthInitializer";
import { AuthNav } from "@/components/ui/AuthNav";

export const metadata: Metadata = {
  title: "PokeChess",
  description: "Where Pokémon meets chess",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body className="min-h-full flex flex-col bg-bg-deep text-white font-body">
        <AuthInitializer>
          <AuthNav />
          {children}
        </AuthInitializer>
      </body>
    </html>
  );
}
