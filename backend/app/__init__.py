"""my_secretary v2 backend.

Four layers, and imports only point downwards, so there are no import cycles
and each layer can change without touching the ones above it:

    api/          the web pages' door in        -> may import features, core
    features/     what the secretary does       -> may import connectors, core
    connectors/   talking to outside systems    -> may import core
    core/         shared kernel (store, Claude, clock, action log) -> imports none of the above

main.py wires them together. The full map is in docs/plan-v2/PLAN.md
("ขั้น 3 · โครงสร้างโค้ด").
"""
