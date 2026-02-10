import { Sidebar, MobileSidebar } from "@/components/sidebar";
import { StarsBackground } from "@/components/ui/stars-background";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <MobileSidebar />
      <main className="relative flex-1 overflow-y-auto overflow-x-hidden p-4 pt-18 md:p-6 md:pt-6">
        <StarsBackground
          starDensity={0.0002}
          twinkleProbability={0.8}
          minTwinkleSpeed={0.4}
          maxTwinkleSpeed={1.2}
          className="pointer-events-none z-0"
        />
        <div className="relative z-10">{children}</div>
      </main>
    </div>
  );
}
