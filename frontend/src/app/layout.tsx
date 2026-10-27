import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Anomaly Detect | Log Analysis",
  description: "Analyze log files, investigate anomalies, and export clean reports.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
