# ANNOTATE-3: bounded annotation overlap reduction

Reduce overlaps is an independent, transient, opt-in display preference. It moves
only result text, never nodes, components, wires, saved data or electrical identity.
It defaults off; both existing annotation modes retain their original placement
when disabled. Existing result freshness and preview suppression apply unchanged.

The pure label_layout module receives measured pixel rectangles from the renderer.
It processes at most 700 labels and 4096 geometry/text obstacles in stable scene
order. Obstacles use conservative actual Canvas item bounding boxes, including
wire/path boxes. These can cover empty space, especially for bent/diagonal paths;
this first version may reject a physically free candidate. No optimal-layout claim.

For each label, try its original rectangle and 24 fixed nearby pixel offsets in
documented order, choosing the first position clear of geometry/text obstacles and
previously placed labels, with a three-pixel gap. Candidate offsets are bounded
by 224 horizontal and 160 vertical pixels, independent of zoom/font size. A sparse
64-pixel spatial index caps each rectangle at 16 indexed cells; larger rectangles
use a bounded global list. All ordered bucket/global IDs merge and deduplicate
lazily, so an early collision does not sort or copy a saturated bucket. At most 200,000
rectangle intersection checks per pass.
The input limits, candidate count and index caps also bound construction/memory.

If all candidates collide, retain the original position and mark that label as
unresolved. If the check budget is exhausted, retain original positions for the
remaining labels. Fallback positions may overlap earlier labels. Unresolved counts
are placement failures/unknowns, not an exact count of colliding pairs. A persistent
panel note tells the user some labels may still overlap and suggests zooming
in or moving components. The algorithm never hides labels to claim success.

Gray dashed decorative guides link displaced node labels to their endpoint dot,
or displaced component blocks to their existing component label. Guides may cross
geometry; they are not wires and have no electrical hit tags. Closest rectangle
edge points keep guide ends outside text. Guides and moved values participate in
Fit; base scroll bounds, saved camera fractions and dirty state stay unchanged
when the preference is toggled or current results arrive/clear.
Because placement can change discontinuously with zoom, Fit makes an initial
estimate then uses bounded shrink-only refinement in this mode. If its 16-step
budget cannot fit the scene, it measures again at the existing 40% zoom floor
and reports the normal zoom-limit diagnostic if content still does not fit.

Acceptance: independently derived gap/intersection/negative-coordinate cases,
determinism, original-position preference, collision-free simple layouts, bounded
fallback/budget/resource inputs and immutable data. Real Tk checks cover measured
boxes, leader/hit isolation, feedback, independent options, camera/dirty/Fit,
current-result freshness, minimum-window controls and installed regressions.
Automatic global routing, movable/persisted annotations and guaranteed separation
in arbitrarily dense layouts remain planned.

`scripts/benchmark_labels.py --repeats 3` reports deterministic placement counts,
budget/fallback information and min/median/max CPU wall times for five bounded
scenes. Unresolved placements are not an exact collision count. No timing gate or
cross-platform responsiveness guarantee is inferred from these diagnostics.
