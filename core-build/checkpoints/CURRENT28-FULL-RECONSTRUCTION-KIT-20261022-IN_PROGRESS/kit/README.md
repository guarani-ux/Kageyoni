# Exact full current28 continuation recovery kit

This small kit reconstructs the complete historical current28/native16 continuation ZIP. It is a recovery recipe and delta, not the full continuation body by itself. The exact target is 469,620,062 bytes, SHA256 `b13c9619efc76e5d5f311755906df65e73c7b2ea9417cee50594b37007b54b04`: 12,688 entries, 11,330 files, 1,358 directories, and 2,790,921,522 raw file bytes. All Library15 parent bytes and adopted historical scopes remain included. Future native18 is diagnostic evidence only. Later current30/31/32 work is outside this snapshot. Full F1–F5 qualification remains false.

On this host, one actual reconstruction completed successfully, followed by independent full readback of all entry bodies, CRCs, metadata, modes, offsets, and compressed hashes. All fourteen raw provider hashes matched afterward. The new derived output's final and partial names were hardlinks to one temporary duplicate inode. Those two names were subsequently released under root approval, after locked archive revalidation. Their historical paths in receipts are no longer present. The exact canonical original remains at `/dev/shm/continuation-current28-lzma/Samsara_Core_Build_Continuation.zip`; that transient host path is not a portable provider or durable custody claim. Execution, readback, and release receipts under `historical-THIS-host-receipts/` record the actual chronology. Earlier held/unrun statements describe earlier states.

## Restore the inputs

1. Verify this kit against the external frozen-manifest receipt supplied with it. The top recipe pins the helper, delta, entry map, and container layout. This kit's new remote custody is not yet established; prior provider custody does not publish the new delta or recipe.
2. Obtain all fourteen complete provider ZIPs from their exact identities in `provider-identities.json` or the top recipe. Use the current Library skill/helper to materialize the pinned Library15 historical file/version and verify its exact size/SHA. The item's latest version is not a substitute for the pinned bytes. For each Git provider use its immutable commit and recipe path through the approved connector, validate transport bytes/part hashes, and follow recursive dependencies. Current26 requires its recursive base chain. `provisioning/recipes/` contains exact retained recipe bootstraps; `provisioning/receipts/` contains prior readback receipts. Inspect historical helpers before use. Native034 has its own recipe; no other checkpoint helper is asserted to implement that schema. No credentials or private transport are embedded in this kit.
3. Copy `providers.example.json` to a working `providers.json` and replace every placeholder with the actual local regular-file path. The helper checks full raw size/SHA of each provider before using its body bytes. The example paths are placeholders, not authority to guess a local source. Original host path maps are excluded from this kit.

The current26 bootstrap is the exact 526,525-byte Git blob `715d7e8035a82047df68403b4c74433648b76088`. The earlier local copy had one extra LF and parsed equivalently, but was a different Git blob. Its provenance distinction and initial package/verification history are retained; the current delta uses canonical bytes.

## Verify and reconstruct

Run the body-only check first. Exit 0 and `ALL_EXPLICIT_ENTRY_BODY_SOURCES_AND_CODEC_CALIBRATIONS_VERIFIED` establish all 12,688 body sources plus two small LZMA codec calibrations.

```bash
python reconstruct_continuation.py --recipe continuation-reconstruction-recipe.json \
  --delta continuation-delta.zip --providers-json providers.json --verify-only
```

Inspect actual host resources and active effect ownership before the full run. The primary agent retains the user's standing authorization for ordinary recovery and maintenance; subordinate agents follow the root's bounded ownership and serial lane decisions. The companion wrapper is the reviewed THIS-host resource model, not a portable guarantee of cache reclamation. Its default invocation is preflight only. It keeps hard RLIMIT_AS at 256 MiB, disk remaining-output plus a 1 GiB reserve, and the root-approved cgroup model including a second target-size memory allowance plus 256 MiB process and 512 MiB memory reserve. It records observed `memory.stat`, protection, OOM events, and peak RSS and guards before body/member reads. A fresh host must inspect its actual resource model rather than infer capacity from old successful counters.

To use the unchanged wrapper, prepare the actual local provider mapping at `providers-current-host.json` beside it (copy your verified working map); this filename is an interface, not a supplied host map. Choose a unique run ID, inspect preflight, and follow the actual root serial/resource decision for execution. It writes a new `full-reconstruction-<run-id>` directory beside itself. It preserves partials/failures and has no automatic retry or deletion. The original helper also accepts a separately chosen existing output directory:

```bash
python reconstruct_continuation.py --recipe continuation-reconstruction-recipe.json \
  --delta continuation-delta.zip --providers-json providers.json \
  --reserve-bytes 1073741824 --output /absolute/new-output/Samsara_Core_Build_Continuation.zip
```

Require actual exit 0, `EXACT_COMPLETE_ARCHIVE_RECONSTRUCTED`, the exact target size/SHA, all raw/compressed entry checks and complete ZIP CRC verification. The helper writes one `.partial`, verifies it, and hardlinks the final name to the same inode. An independent byte readback established this host's result; its retained script under `historical-tools/` contains historical host paths and must be reviewed before adaptation. No second full physical extraction or new runtime qualification is claimed.

## Mapping and remaining limits

The delta stores one ordered body/metadata record per entry, exact local headers and central-directory/trailer bytes, and 123 otherwise unmapped unique bodies totaling 19,234,449 raw bytes (133 path occurrences). Body references use exact provider raw ZIPs, exact provider members, two proved prefixes, or delta members. Prefix origin remains UNKNOWN; only byte equality is established. No nested archive or historical payload was dropped.

Exact compressed bytes depend on matching LZMA encoder behavior. The small calibrations and every complete compressed-body SHA plus final target SHA fail closed on a different bitstream. The actual full run and independent readback succeeded with the observed host implementation. Candidate source/gate identities are retained in the top recipe and delta proofs. Old prepared worlds require their matching historical runtime; this kit does not authorize interpreting their observations as new current28 results.

New kit remote readback and any Library same-item update remain separate custody steps. No new Library version or full-release claim is made here. All SHA references to the target are external to that target ZIP; the frozen manifest excludes its own body, and the receipt pins it externally.
