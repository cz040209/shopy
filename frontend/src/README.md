# Source layout

- `app/` contains Next.js routes, layouts, and route-level styles only.
- `components/ui/` contains reusable, presentation-only building blocks.
- `components/layout/` contains shared application chrome.
- `features/` owns feature-specific components, state, and data.

Keep new code close to the feature that uses it. Promote a component to `components/ui` only when it is shared across unrelated features.
