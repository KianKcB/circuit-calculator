# ANNOTATE-2: optional component current and power labels

The Component I / P checkbox adds read-only measurements beside component labels,
independently of Node voltages. Both options default off per window and are
transient. No document/schema/dependency or solver changes.

Each block displays signed current I, the positive-current direction `+I: first →
second`, and signed power P with absorbed/delivered/zero classification. First and
second are the resistor's a/b, voltage source's plus/minus, or current source's
from/to terminals. Negative I means flow opposite the displayed positive direction.
Positive P is absorbed, negative P delivered; exact zero is zero. There is no new
tolerance, absolute-value conversion, inferred individual wire current or animated
flow arrow. Rotating a symbol never changes its terminal identities or sign rule.

Pure annotations.component_annotations reads existing ElementResult values from a
current accepted DCResult. It never recomputes I or P, solves, or mutates state.
Missing result/branch entries yield no label; non-finite displayed values are
rejected by the existing nine-significant-digit SI formatter. The caller must
establish revision correspondence, as for selected-item inspection.

The renderer uses the actual bounding box and anchor of each existing component
label. Numeric generated indexes connect that box to the exact component identity,
without evaluating user names as Canvas tag expressions. Blocks go below the
existing text, except above an existing above-symbol label; left-side labels keep
their right edge so measurement text extends away from the symbol. Font size stays
readable during zoom. Decorative tags cannot change electrical hit identities.

Both annotation types participate in Fit while base scroll bounds remain unchanged.
Toggles, result arrival and clearing preserve saved camera fractions/dirty state.
Explicit Fit/zoom/pan retain normal saved-camera behavior. Drag previews suppress
both annotation types. Edits/history/new/open/new solves clear obsolete values;
failed or rejected stale worker jobs cannot restore them.

Dense layouts may overlap labels, including between neighboring components or
terminals. Automatic collision avoidance and movable labels remain planned.
Acceptance covers analytical resistor and signed voltage/current-source power,
reference and orientation invariance, missing/zero/tiny/range values, all four
rotations, legacy parallel symbols, special names, decorative tags, Fit/camera,
both toggles, preview/freshness and source/installed regression workflows.
