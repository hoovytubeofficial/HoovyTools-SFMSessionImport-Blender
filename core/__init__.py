"""
core/  -  part of HoovyTools
==========================

Shared plumbing every feature depends on.

Nothing in here knows about the SFM pipeline; everything else
depends on it. If a module here imports from `session/`,
`importers/` or `tools/`, the layering has been broken.
"""
