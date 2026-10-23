"""Reference data: quantities, recipes, immutable shards and an append-only provenance log.

Layout of a reference tree (see CLAUDE.md):

- ``assumptions.toml``: the allowed names in a recipe's ``assumes``;
- ``systems.toml``: the systems recipes may use, marking those in this repository;
- ``quantities/<name>.toml``: input schema (``input``), key fields (``key``), output, canonical form;
- ``recipes/<system>/<name>.vN.toml``: active recipes (``id``, ``quantity``, ``system``,
  ``template``, ``parser``, ``assumes``); files are never edited;
- ``recipes-retired/<system>/<name>.vN.toml``: retired recipes, moved there unchanged;
- ``data/<quantity>/NNNN.jsonl``: active (believed correct) shards; line 1 is the header
  ``{"format":1,"quantity":...}``, every further line is a row with the key fields and ``out``;
- ``retracted/<quantity>/NNNN.jsonl``: retracted shards, moved there unchanged;
- ``provenance/<quantity>.jsonl``: append-only events.

Events (all have ``event``, ``date``, ``host``, ``tool_commit``; ``tool_commit`` is a commit of
origin/main whose tooling (tools/, crosscheck/) equals the tooling that ran):

- ``produced`` / ``confirmed`` / ``disagreed``: ``shard``, ``sha256``, ``recipe``, ``recipe_sha256``,
  ``system``, ``system_version``, ``assumes``; ``disagreed`` also ``mismatches`` (list of keys).
  For in-repository systems ``system_version`` is the commit at which the reproduction ran
  (``git checkout`` it to reproduce) and ``toolchain`` records the Python (and rustc) versions;
  reproductions may be recorded on a branch, since pull requests are merged with merge commits;
- ``retracted``: ``shard``, ``sha256``, ``reason``, optional ``superseded_by``;
- ``inherited``: ``shard``, ``sha256``, ``source``, ``source_sha256``, ``excluded`` (list of keys):
  every row of ``shard`` whose key occurs in ``source`` and is not excluded is byte-identical to the
  source row and inherits the source's support;
- ``recipe_retired``: ``recipe``, ``reason`` (``outdated``: it no longer runs with current software,
  its reproductions keep counting; ``bug``: the recipe was wrong, its reproductions no longer
  count), ``explanation``.

Status is derived from the log, never stored.
"""
