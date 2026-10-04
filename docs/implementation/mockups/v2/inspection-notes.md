# Mockup inspection notes — revision 2

These notes distinguish visual concept coverage from implementable behavior. The [UI specification](../../ui-design-spec.md) is authoritative.

## Review outcomes

- The first compact board included redundant full-app previews and ambiguous width annotation. A targeted edit removes those previews, shows only compact studies, and measures the entire 200-pixel strip including its button.
- The first Desktop/Sync/About board omitted the About content. A targeted edit explicitly includes all three complete settings views.
- The platform board initially reintroduced app titles and macOS traffic-light controls into compact strips. A targeted edit removes them from compact on all three platforms while preserving native chrome on the main windows.
- Existing Python top-level windows/message boxes were checked against the coverage inventory. A seventeenth board adds the daily mode breakdown and Reset Today's Stats confirmation/outcomes.
- An eighteenth board explicitly pictures completion, unsaved drafts, disconnect, and credential expiry rather than relying on descriptions beside the larger screens.
- Ordinary main-window previews repeated inside some boards are illustrative. They do not add extra product destinations, standalone windows, or controls.
- First-stable-release boards and later-release concepts are separated. No generated image authorizes a feature expansion or marks an implementation task complete.

## Differences to resolve in the component prototype

| Area | Written implementation rule |
| --- | --- |
| Main navigation | Timer, Tasks, Reports, Settings; use the same component in all screens |
| Settings navigation | Eight categories specified in the UI document; horizontal/reduced category variants in some images are incidental |
| Timer actions | Start/Pause/Resume primary; Finish during focus, Skip break during breaks. Incidental Stop/Reset labels in secondary previews do not add commands |
| Phase colors | Use the shared work/break tokens; red is reserved for errors/destructive actions, not normal focus |
| Interrupted reports | Treat interruptions as neutral session outcomes; do not imply a fault or shame the user |
| Main compact entry | Add a clear entry in the main toolbar/menu and tray; some generated timer panels omit that entry |
| Exit during focus | “Keep running” means Continue in background, only with a tested reopen path; it does not survive actual process termination |
| Data status | “Saved on this device” follows successful local persistence. Offline sync alone is not local save failure |
| Sync settings | “Your data is stored only on this device” applies while sync is off; connected state must explain what is synchronized |
| Import validation | Abort invalid mandatory data safely; partial import requires explicit reviewed selection, not an automatic silent skip |
| Restore/reset | Create the protective backup first; transaction failure leaves current records untouched |
| Sample charts/dates | Examples are not coherent production data or calendar fixtures; compute labels/aggregates from real records |
| Platform chrome | Use native decorations and system dialogs; illustrated controls are not evidence of compositor or notification support |
| Compact dimensions | Logical defaults, not fixed raster dimensions; larger text/hours grow the strip; minimum button target stays usable |
| Task form validation | Task estimates remain session counts; an incidental minutes field in the errors board illustrates validation, not a task-specific duration feature |
| Completion copy | Use “If break auto-start is enabled”; the incidental word “external” in the completion note does not add an integration |
| Welcome copy | Local-first and no required account; do not promise data never leaves the device if optional sync is enabled |
| Legacy project import | Import project links only when present in the source; 0.3.1 data without projects uses an explicit default/unassigned mapping |
| Desktop capability variants | The unavailable-tray banner is a separate variant; disable close-to-tray when no tested reopen path exists |
| Accessibility | Focus, contrast, semantics, readable text and no tick announcements require actual prototype checks |

The compact button, context-menu discovery, all settings categories, recovery paths, report/task dialogs, and three-platform layout concepts are the key visual-review checkpoints. All 18 selected PNGs passed signature/chunk-CRC/decompression/scanline validation, and all 48 local document references present during the validation pass resolved. The inventory contains 74 uniquely identified surfaces/states. Results, dimensions, and SHA-256 hashes are recorded in `asset-validation.json`. These checks verify the design artifacts, not application behavior.

## Remaining design validation

Static raster images cannot verify tab order, modal focus restoration, assistive-technology names, 200% text behavior, compositor placement, shortcut permissions, or update safety. These remain explicit M1/M5 prototype and packaged-build gates. UI code must not copy fabricated sample data, duplicate sidebars, or extra controls from an incidental preview.

