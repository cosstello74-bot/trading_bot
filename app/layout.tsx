import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DEN v1 — Decision Engine Network",
  description:
    "Find the perfect laptop in under 60 seconds with a deterministic decision engine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
