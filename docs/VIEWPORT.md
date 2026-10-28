# GUI-6: renderer separation and circuit navigation

Contract, 2026-10-28. Preserve model, route geometry and project v3.

Move Canvas drawing into canvas_renderer.py, keeping dialogs/actions/workers and
transient routing in gui.py. Renderer returns pixel bounds for tagged circuit
items (symbols, leads, wires, dots, labels/reference), excluding decorative grid,
selection handles and pending previews. This keeps growing visual code separate
from controller/file logic without creating a new GUI framework.

Fit Circuit (or F on the canvas) measures actual rendered bounds, adjusts zoom
within [0.4, 2.5] with a 32-pixel margin, remeasures fixed-size text and centers the
result. Extreme circuits may still require scrolling at minimum zoom; report that
limit. 100% resets zoom to 1 while preserving the viewed world center. Existing
plus/minus zoom also preserves world center, rather than jumping toward the origin.
Resizing retains the old world center. View-only changes preserve simulation
results/history but update project dirty state, as existing pan/zoom do.

Scroll bounds use circuit bounds with half-viewport padding, allowing every
region to be centered. No position/connectivity edits occur during navigation.
Geometry previews retain the previous saved bounds. New/default documents center
their content; explicit saved view fractions remain the restore input. The v3
field meanings stay unchanged (Tk leading scroll fractions), but older saved
fractions can display differently because renderer bounds/fonts/viewport differ.
This is documented camera compatibility, not a graph migration. Exact screen
pixels across versions/platforms/window sizes are not promised.

Pure viewport.py owns bounded zoom, fit and scroll-fraction arithmetic; it has no
Tk/NumPy dependency. Renderer remains Tk-only at runtime through the passed Canvas;
importing it must not create a window. No new dependencies; local package 0.8.0.

Acceptance: independent zoom/fraction arithmetic, nonfinite/type/range cases,
empty/tiny/large/signed bounds, actual visible circuit/text fit, center-preserving
zoom/resize, selection/preview exclusion, graph/result/history invariance, saved
view round trips, all existing Tk interactions, fresh package imports and visual QA.
