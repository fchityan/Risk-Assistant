# Risk Assistant — UI Style Guide

Use this when adding screens, panels, or HTML fragments so new UI matches the existing compliance-dashboard look.

***

## Design intent

Risk Assistant presents **evidence-grounded reputational screening** for analysts. The visual language should feel:

- **Professional and audit-ready** — light surfaces, structured tables, clear hierarchy
- **Trust-oriented** — navy primary palette, restrained gradients, no playful clutter
- **Scannable** — metric cards up top, tabbed detail below, severity encoded with consistent color
- **Honest about data source** — mock/example mode uses amber warnings; live vs bypass vs backend status appears in the sidebar

Avoid decorative animation, dark main-canvas themes, or dense monospace body text (monospace is reserved for rule-engine method labels).

***

## Typography

### Font families

| Role | Font | Weights used | Applied to |
|------|------|--------------|------------|
| **Display / headings** | [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk) | 500, 600, 700 | `h1`–`h5`, `.header-standard`, panel titles, sidebar brand, assessment headings |
| **Body / UI** | [Manrope](https://fonts.google.com/specimen/Manrope) | 400–800 | `.stApp`, labels, table cells, captions |

Fonts load via Google Fonts in `base.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
```

### Type scale

| Token / class | Size | Weight | Use |
|---------------|------|--------|-----|
| `.main-title` | 49px (26px mobile) | 700 | Hero product name |
| `.main-subtitle` | 13px (17px mobile) | 400 | Hero one-liner |
| `.header-standard`, `.assessment-title`, `.section-title`, `.memo-preview-title`, `.reviewer-decision-title` | 24px (`--assessment-header-size`) | 700 | Section and tab panel headers |
| `.rub-rule-title` | 18px | 700 | Rubric rule group headings |
| `.sb-title` | 22px (20px mobile) | 800 | Sidebar app name |
| Body / table cells | 13px | 400–500 | Default content |
| Table headers | 12px | 500 | Column labels |
| `.metric-label` | 11px | 700 uppercase | Metric card labels |
| `.chip` | 10.5px | 700 | Hero capability chips |
| `.metric-caption` | 10.5px | 400 | Secondary metric line |
| `.sb-system-label` | 12px | 700 uppercase | Sidebar section labels |

### CSS variables (headings)

```css
:root {
  --assessment-header-size: 24px;
  --assessment-header-weight: 700;
  --assessment-header-color: #1a2f5e;
}
```

Prefer `.header-standard` or the assessment/section title classes over raw `h3`/`h4` in new HTML so sizes stay consistent.

***

## Color palette

### Core neutrals

| Name | Hex | Usage |
|------|-----|--------|
| Navy heading | `#1a2f5e` | Headings, `--assessment-header-color` |
| Navy body | `#1f2f5b` | Primary text, input text |
| Slate body | `#2a3a54` | Table cells, panel body copy |
| Muted label | `#597294`, `#5f7798`, `#5f7290` | Captions, table headers, stat labels |
| Placeholder | `#6a7fa5` | Input placeholders |
| Border light | `#dce6f7`, `#d6e5fb`, `#d5e3fb`, `#e7edf7` | Cards, shells, tables |
| Surface tint | `#f7f9fc`, `#f8fbff`, `#f5f8ff` | Table header bg, inputs, code/method blocks |
| Canvas | `#ffffff` | Main app background |

### Brand accents

| Name | Hex / gradient | Usage |
|------|----------------|--------|
| Primary blue | `#2f6fed`, `#2563eb` | Links, kv values, active tab underline, material stat |
| Primary gradient (CTA) | `linear-gradient(90deg, #1f70cf, #119385)` | Primary buttons (Run Screening) |
| Sidebar gradient | `linear-gradient(190deg, #061a3a, #0a2d5d 58%, #07214a)` | Sidebar background |
| Sidebar text | `#edf4ff`, `#bfd4f5` | Sidebar copy |
| Hero teal wash | `rgba(15,157,141,0.16)` | Hero radial highlight |
| Hero shield | `#61a4ff` → `#2456d6` | Decorative shield orb |

### Semantic — risk & severity

Use these consistently for severity, support bands, and metric emphasis:

| Semantic | Text / accent | Background (badges) | Classes |
|----------|---------------|---------------------|---------|
| High / critical | `#eb3131`, `#f04438`, `#e23a33`, `#c55e31`, `#cc4e68` | `#ffeceb` | `.kf-sev-high`, `.rf-badge-high`, `.metric-v1`, `.metric-v2`, `.rbd-high` |
| Medium | `#d78619`, `#f08c00` | `#fff3dc` | `.kf-sev-medium`, `.rf-badge-status`, `.rbd-medium` |
| Low / positive | `#1d9a64`, `#129069`, `#12a66a`, `#0f9d8d` | `#def7ef`, `#def7f6` | `.kf-sev-low`, `.metric-v3`, `.metric-v5`, `.rbd-low` |
| Info / coverage | `#2d6be3`, `#2d6be3` | `#e8f0ff`, `#ece9ff` | `.metric-v4`, `.rbd-material` |
| Disposition accent | `#0f9d8d` | — | Disposition highlights in memo preview |

### Mock / warning

| Element | Colors |
|---------|--------|
| `.mock-badge` | bg `#f59e0b`, text `#1f2937` |
| `.mock-banner` | bg `#fff7df`, border `#f6c25f`, text `#8b5a0b` |

### Panel icon gradients

Each dashboard panel uses a **22×22px rounded square** (7px radius) with white glyph and a section-specific gradient:

| Panel | Prefix | Gradient |
|-------|--------|----------|
| Key findings | `kf` | `#2f7de1` → `#1c62d6` |
| Evidence | `ev` | `#56cf9b` → `#2da879` |
| Risk flags | `rf` | `#ff6a60` → `#f13c35` |
| Rule determination | `rbd` | `#8f79ff` → `#6f57db` |
| Triggered rules | `trg` | `#7aa4ff` → `#4d72f3` |
| Audit | `aud` | `#58d7a0` → `#2aa579` |
| Full memo | `fm` | `#66a9ff` → `#2f76df` |
| Rubric | `rub` | `#8b79ff` → `#6f57db` |

Metric row icons (32×32px, 10px radius) use soft flat tints: `.i-risk`, `.i-evidence`, `.i-entity`, `.i-coverage`, `.i-disposition`.

***

## Layout & spacing

| Token | Value | Usage |
|-------|-------|--------|
| Max content width | `1550px` | `.block-container` |
| Sidebar width (desktop) | `272px` | `@media (min-width: 1024px)` |
| Sidebar width (mobile) | `min(86vw, 300px)` | `@media (max-width: 1023px)` |
| Main padding top | `0.85rem` | Default; `0.35rem` on mobile |
| Card padding | `10–16px` | Shells, hero, metric cards |
| Grid gap (metrics) | `12px` | `.metric-grid` (5 → 2 → 1 columns by breakpoint) |
| Assessment columns | 1 col → 2 col at `1200px` | `.assessment-columns` |

### Breakpoints

| Breakpoint | Behavior |
|------------|----------|
| `max-width: 1023px` | Single-column assessment; hero shield hidden; larger touch-friendly subtitle; sidebar overlay disabled; kv rows stack |
| `min-width: 1024px` | Fixed sidebar width |
| `min-width: 1200px` | Two-column assessment + scope grid |

***

## Shape, border, shadow

| Element | Border radius | Border | Shadow |
|---------|---------------|--------|--------|
| Hero | `18px` | `1px #d5e3fb` | `0 14px 28px rgba(24,47,82,0.06)` |
| Metric / panel cards | `14px` | `1px #d2e2fb` / `#d6e5fb` | `0 8px 18px rgba(24,47,82,0.07–0.08)` |
| Shell panels | `12px` | `1px #dce6f7` | none (flat inside tabs) |
| Tables inner | `8px` on wrap | `1px #e7edf7` | none |
| Chips | `999px` (pill) | `1px #cfe0fb` | none |
| Buttons / inputs | `12px` | see forms | focus ring below |
| Badges | `6px` | none | none |
| Tab container | `16px` top corners | `1px #dce6f7` | subtle tab shadow |

Focus ring for inputs: `border-color: #7aa7f0`, `box-shadow: 0 0 0 2px rgba(47,111,237,0.18)`.

***

## Component patterns

### 1. Shell + head + icon (dashboard panels)

Standard structure for Evidence, Risk Flags, Rules, Audit, Memo, Rubric tabs:

```html
<div class="ev-shell">
  <div class="ev-head">
    <div class="ev-title-wrap">
      <span class="ev-icon">…</span>
      <span class="header-standard">Evidence</span>
    </div>
    <span class="ev-viewall">View all</span>  <!-- optional -->
  </div>
  <!-- table or content -->
</div>
```

Replace `ev` with `rf`, `rbd`, `trg`, `aud`, `fm`, `rub`, or `kf` per panel. Always pair with `.header-standard` for the title text.

### 2. Data tables

- Wrapper: `{prefix}-table-wrap`
- Table: `{prefix}-table`
- Header row: `#f7f9fc` background, `#7f8b9b` text, `12px`
- Body cells: `#2a3a54`, `13px` (audit `12px`)
- Borders: `#e7edf7` grid lines
- Long text columns: allow `word-break: break-word`; ID columns: `nowrap` + ellipsis

### 3. Metric cards (top summary row)

Five-column grid of `.metric-card` blocks inside `.metric-grid`:

```html
<div class="metric-grid">
  <div class="metric-card">
  <div class="metric-top">
    <span class="metric-icon i-risk">🛡️</span>
    <div class="metric-label">Overall Risk</div>
  </div>
  <div class="metric-v1">Medium Risk</div>
  <div class="metric-caption">medium</div>
</div>
</div>
```

Use `.metric-v1` … `.metric-v5` for the primary value color coding (risk, evidence, entity, coverage, disposition).

### 4. Key–value rows

Built via `_kv_rows()` in `app.py`:

```html
<div class="kv-row">
  <div class="kv-label">Country</div>
  <div class="kv-value">Singapore</div>
</div>
```

Labels are bold navy (`#1e3560`); values are link-blue (`#2563eb`). Escape all dynamic values with `html.escape()`.

### 5. Rule callouts

```html
<div class="rule-box">CASE_HIGH_01: critical adverse signal…</div>
```

Light blue fill, left accent bar `#2d6be3`.

### 6. Severity badges (risk flags table)

Map backend severity to badge class via `_severity_badge_class()` in `app.py`:

```html
<span class="rf-badge rf-badge-high"><span>●</span>High</span>
<span class="rf-badge rf-badge-medium"><span>●</span>Medium</span>
<span class="rf-badge rf-badge-low"><span>●</span>Low</span>
<span class="rf-badge rf-badge-status">open</span>
```

### 6b. Shared layout utilities (`base.css`)

| Class | Use |
|-------|-----|
| `.metric-grid` | Top summary metric row (responsive columns) |
| `.hero--flush` | Hero with no bottom margin (pairs with form row) |
| `.coverage-notes` | Assessment coverage footnote |
| `.table-empty` | Centered empty table cell (via `_table_empty_row()`) |
| `.panel-head-row`, `.panel-icon-lg` | Right-column panel headers (memo preview, reviewer) |
| `.memo-preview-*`, `.disposition-accent`, `.disposition-rationale` | Memo preview body |
| `.sidebar-divider`, `.sidebar-spacer`, `.form-spacer` | Vertical rhythm spacers |
| `.reviewer-label`, `.disclaimer-bar` | Reviewer form labels and footer disclaimer |
| `.checklist-shell`, `.kf-title-wrap` | Checklist tab header shell |

### 7. Stat grid (rule determination)

`.rbd-stats` — five equal columns with large numeric `.rbd-value` and semantic color classes `.rbd-high`, `.rbd-medium`, `.rbd-low`, `.rbd-material`, `.rbd-tier`.

### 8. Hero block

```html
<div class="hero">
  <div class="main-title">Risk Assistant</div>
  <div class="main-subtitle">…</div>
  <div class="chip-row">
    <span class="chip">Bright Data</span>
  </div>
</div>
```

Optional right column: `.hero-shield` in `.hero-shield-wrap` (hidden on mobile via `.hero-right`).

### 9. Sidebar (static HTML in `app.py`)

Classes prefixed with `sb-`: brand row, nav items (`.sb-nav-item-active` for current), system card, profile block. Dynamic strings (backend URL, status) are concatenated in Python — keep HTML structure stable.

### 10. Streamlit form controls

Styled globally in `base.css` — do not override per-widget unless necessary:

- Labels: `#2f466b`, weight 700
- Inputs/selects: `#f8fbff` fill, `#cadaf4` border, `#1f2f5b` text
- Primary buttons: blue-teal gradient, full width in form columns

Use `st.container(border=True)` — styled via `[data-testid="stVerticalBlockBorderWrapper"]`.

### 11. Tabs

Streamlit `st.tabs` — styled as connected card: rounded top bar + bottom panel with shared `#dce6f7` border. Active tab: `#2f6fed` bottom border.

***

## Content & markup rules

1. **Escape user data** — always `html.escape()` for subject names, summaries, URLs, rule text injected into `unsafe_allow_html=True` blocks.
2. **Prefer classes over inline styles** — use utilities in `base.css` / column classes in `panels.css`; do not add new inline `style=` attributes in `app.py`.
3. **Use semantic severity classes** — map backend enums to `.kf-sev-high|medium|low` or badge variants; do not invent new red/amber/green hex values.
4. **Section titles** — use `.header-standard` or `.section-title`, not bare `<b>` tags.
5. **Empty states** — muted `#5e7392` or `#7f8b9b` copy, centered in table colspan rows (see `.kf-empty` pattern).
6. **Monospace** — only for machine identifiers (e.g. `.rbd-method` showing `rule_based_v1`).

***

## File organization

| File | Responsibility |
|------|----------------|
| `frontend/static/base.css` | App shell, sidebar, hero, metrics, forms, tabs, assessment layout, responsive rules |
| `frontend/static/panels.css` | Tab panel shells and tables (`ev-`, `rf-`, `rbd-`, etc.) |
| `frontend/style_loader.py` | Loads CSS in order and injects via `inject_app_styles()` |
| `frontend/app.py` | HTML fragments; no large `<style>` blocks |

When adding styles:

- **Global / layout** → `base.css`
- **New dashboard panel** → `panels.css`, following the `{prefix}-shell` convention
- Call `inject_app_styles()` once at startup (already done in `app.py`)

***

## Status & mode indicators

| UI state | Visual treatment |
|----------|------------------|
| Mock / example profile | `.mock-badge` in sidebar + `.mock-banner` in main area |
| Backend connected | Sidebar status: “live api connected” |
| Frontend live bypass | Sidebar status: “live mode” |
| Backend unavailable | Caption from `backend_status_message`; example profile loaded |

Do not hide mock mode — analysts must always know when data is not from a completed pipeline run.

***

## Accessibility notes

Current implementation is **visual-first** (Streamlit + HTML). When extending:

- Keep contrast for body text on white (navy on white meets WCAG for normal text)
- Severity should not rely on color alone — pair with text labels (`High`, `Medium`, `Low`) or bullets `●`
- Touch targets on mobile: chips and expanders get larger padding in the `1023px` breakpoint
- Prefer readable font sizes ≥12px for table content

***

## Quick checklist for new UI

- [ ] Uses Space Grotesk for titles, Manrope for body (via global CSS)
- [ ] Panel follows `{prefix}-shell` / `{prefix}-head` / `{prefix}-icon` pattern
- [ ] Tables use wrap + `#f7f9fc` header row
- [ ] Dynamic text escaped with `html.escape()`
- [ ] Severity uses existing semantic color classes
- [ ] Styles added to `base.css` or `panels.css`, not inline
- [ ] Mobile layout tested at ≤1023px width
- [ ] Mock/live status remains visible when using sample data

***

## Related docs

- [frontend/README.md](../frontend/README.md) — setup, modules, runtime modes
- [integration.md](integration.md) — API flow and report mapping
- [architecture.md](architecture.md) — backend pipeline and report schema
