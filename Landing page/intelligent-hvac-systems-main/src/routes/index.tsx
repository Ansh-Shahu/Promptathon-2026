import { createFileRoute } from "@tanstack/react-router";
import { Header } from "@/components/site/Header";
import { Hero } from "@/components/site/Hero";
import { Features } from "@/components/site/Features";
import { HowItWorks } from "@/components/site/HowItWorks";
import { SocialProof } from "@/components/site/SocialProof";
import { CTA } from "@/components/site/CTA";
import { Footer } from "@/components/site/Footer";

export const Route = createFileRoute("/")({
  component: Index,
  head: () => ({
    meta: [
      { title: "HVAC-IQ Solutions — Predictive Maintenance for Industrial HVAC" },
      { name: "description", content: "AI-driven predictive maintenance and optimization for industrial HVAC. Real-time monitoring of AHUs, chillers, pumps, and compressors." },
      { property: "og:title", content: "HVAC-IQ Solutions — Predictive HVAC Intelligence" },
      { property: "og:description", content: "Maximize uptime, minimize costs, and prevent failures across your chilled water system." },
    ],
  }),
});

function Index() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <Hero />
        <Features />
        <HowItWorks />
        <SocialProof />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
