# R1 inherited source import gate

The Situation Architecture branch is not an integrated Kageyoni v11 release until the inherited engine source is present in Git.

Required inherited paths include at minimum:
- kageyoni/engine.py
- kageyoni/persistence/ and migrations through the v11 trust schema
- kageyoni/v11/ runtime, enforcement, adaptive, integrity and integration modules
- kageyoni/workspaces/ world, registry, documents, repository and pipeline services
- kageyoni/composition/ Frames/governor services
- kageyoni/intelligence/ node, learning, method/transfer/network services used by adapters
- inherited tests including test_v11*, v10/inherited regressions and their fixtures

Source authority for import is the preserved v11 foundation plus demonstrated Scar repairs. Situation-only CI is not release qualification.

The release CI intentionally fails when these inherited paths are absent. Do not remove that failure gate; satisfy it by importing/integrating the real source.
