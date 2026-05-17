## Hero split layout

Currently the hero stacks: centered text on top, full-width 3D system image below. You're right — a side-by-side split feels more premium and "product-led" for a B2B SaaS.

### Changes (only `src/components/site/Hero.tsx`)

**Desktop (lg+)**
- Two-column grid: text on the **left** (5/12), 3D system + overlays on the **right** (7/12).
- Text left-aligned (badge, H1, sub-headline, CTAs).
- Image card slightly tilted/elevated with stronger shadow so it reads as the hero visual.
- Status overlay positions recalibrated for the new aspect (image will render taller/narrower).

**Tablet & mobile (<lg)**
- Falls back to the current stacked layout: text on top (centered), image below full-width.
- Overlays repositioned for the wider mobile aspect.

**Kept as-is**
- Copy, headline, sub-headline, CTA buttons, badge.
- Overlay style (pulsing green check, metric values).
- "LIVE • System Telemetry" badge on the image.
- Background gradient and radial glow.

### Out of scope
- Header, Features, How-it-works, Social proof, CTA, Footer — untouched.
- Design tokens / colors — untouched.
