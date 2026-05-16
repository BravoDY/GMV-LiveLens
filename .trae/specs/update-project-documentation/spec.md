# Update Project Full Documentation Spec

## Why
The project has recently implemented several critical features, including advanced OCR engine support (`ddddocr`), automatic dataset collection, global capture interval settings, relaxed page binding rules, screenshot timeout resilience, and refined GMV surge/drop confirmation logic. The `GMV-LiveLens项目全量说明书.md` needs to be updated to reflect these new capabilities so future maintainers and AI assistants have an accurate source of truth.

## What Changes
Update `.trae/documents/GMV-LiveLens项目全量说明书.md` with the following:
- **Global Settings**: Document the global OCR engine switcher and global capture interval (e.g., 0.5s) in the top navigation bar, replacing per-task frequency.
- **OCR Engine (ddddocr)**: Add `ddddocr` as a dedicated engine for artistic fonts and high-interference backgrounds (captcha-like). Explain that its "pure number" restriction was removed, relying instead on `AMOUNT_PATTERN` regex for cleanup (e.g., handling "羊49955" to "49955").
- **Auto-Dataset Collection**: Document the mechanism where every cropped GMV image (from manual tests or backend scheduler) is saved to `data/ocr_datasets/` formatted as `Platform_Shop_Value_Timestamp.png` for future fine-tuning.
- **Relaxed Binding Rules**: Explain that UI and Backend no longer strictly block users from binding non-target or "old" pages. Any selected page can be bound and will immediately transition to `edge_target_page_ready` for preview and OCR.
- **Screenshot Resilience**: Document the 5-second timeout fallback for Playwright's `page.screenshot`, which retries without `animations="disabled"` if font loading causes a hang.
- **Surge/Drop Judgment Logic**: Document that any drop immediately triggers `suspect`. Drops or >5x surges trigger a warning state that requires `max(3, confirm_count + 1)` continuous confirmations to "auto-heal" and accept the new value.

## Impact
- Affected specs: Documentation only.
- Affected code: 
  - `.trae/documents/GMV-LiveLens项目全量说明书.md`

## ADDED Requirements
### Requirement: Update Existing Technical Documentation
The system SHALL have an up-to-date `.trae/documents/GMV-LiveLens项目全量说明书.md` that acts as the single source of truth for all current functionalities.

#### Scenario: Success case
- **WHEN** a developer or AI reads the documentation
- **THEN** they will find accurate descriptions of the global interval, ddddocr integration, auto-dataset generation, relaxed binding, screenshot timeout fallbacks, and the latest surge/drop judgment logic.