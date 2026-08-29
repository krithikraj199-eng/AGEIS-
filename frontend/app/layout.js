import "./globals.css";

export const metadata = {
  title: "AEGIS Ω — Command Center",
  description: "Autonomous Institutional Intelligence & Self-Healing Operating System",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
