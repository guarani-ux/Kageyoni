# Raw journal findings

The journal contains preimages from the retained pre-v23/schema22 state of this fixture. It does not describe the final native034 absence transaction.

Its five valid nonce-checksummed records cover pages1,372,156,155,188. The header records372 original pages, schema cookie214 and change counter402; the retained final database has467 pages, cookie292 and counter428. Four nonheader journal pages match the same fixture’s pre-v23 backup byte for byte. Page1 also matches except the backup-rewritten change/schema counters. No other retained image matches all four;73 other pre-v23 images match only the two deterministic schema/index pages.

Raw record decoding identifies pages155/156 as engine_versions and its index, page188 as migration_checks containing versions3–22, and page372 as a schema leaf. The final image contains migration rows3–34, one current registration and one absence receipt. It has492 decoded schema objects and no duplicate names in that raw tree.

The journal’s old schema leaf372 contains row372, v11_execution_receipts. The final image contains the same definition on leaf356, which the journal does not restore. This stale-leaf overlap is consistent with the duplicate-table error observed during the previously authorized copied recovery. No recovery was performed in this forensic commission.

The source fixture installs the earlier migrations before creating the synthetic workspace and later native033/034 activity. Distinct neighboring fixtures have different workspace IDs and creation seconds. The exact four-page match is unique to the retained pre-v23 backup in the journal-bearing fixture directory. These facts identify an earlier schema stage; they do not establish why the journal remains or rule on unrecorded file-incarnation history.

All33 original directory files still match the pre-copy barrier hashes. The failed recovery copy also matches its separate after-failure inventory. Only raw read-only byte parsing and reports were performed. Prior test passes, collector failure and copied recovery failure remain separately preserved.
