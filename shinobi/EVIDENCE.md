# Kageyoni-Shinobi Evidence

Empirical test outcomes and verification records for Kageyoni-Shinobi implementation:

1. **Identity Stability Across Process Restarts**:
   - `test_init_and_stable_identity_across_fresh_instances` proves that a participant initialized under a `--home` path persists its Kageyoni character record and node binding across fresh Python runtime lifecycles.

2. **Dialogue Ledgering**:
   - `test_begin_reply_flow_and_dialogue_ledgering` demonstrates that host messages emit verified `dialogue_turn` rows in the Kageyoni engine database.

3. **Authority Bounds**:
   - `test_authority_boundary_enforcement` verifies that unauthorized actions (such as attempting `write_note` when `allow_write` is `False`) are blocked before filesystem mutation occurs.

4. **Return Adjudication**:
   - `test_propose_and_adjudicate_return` proves candidate returns can transition to `ACCEPTED`, updating cognitive configuration attributes and qualifying associated lessons.

5. **Interruption Recovery**:
   - `test_process_death_and_recover` validates that encounters interrupted mid-execution transition to `interrupted` status with explicit observation of uncertainty.

6. **Static Scout Isolation**:
   - `test_scout_surfaces_forms_and_remains_read_only` confirms that `scout_horizon` discovers unactivated candidates via token overlap without executing organ code.
