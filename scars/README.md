# Scar Ledger

A **Scar** is a demonstrated failure whose cause, repair, and regression evidence are preserved.

Loop:

1. Probe.
2. Reproduce.
3. Identify the smallest upstream cause.
4. Add or qualify the failing probe.
5. Repair.
6. Reprobe plus valid neighboring controls.
7. Generate repair-derived attacks.
8. Commit the result.
9. Widen regression only after the local gate is clean.

A repair does not exist until it is committed.
