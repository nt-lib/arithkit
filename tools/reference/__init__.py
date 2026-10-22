"""Reference data: quantities, recipes, immutable shards and an append-only provenance log.

Layout of a reference tree (see CLAUDE.md):

- ``assumptions.toml``: the allowed names in a recipe's ``assumes``;
- ``quantities/<name>.toml``: input schema (``input``), key fields (``key``), output, canonical form;
- ``recipes/<system>/<name>.vN.toml``: immutable recipes (``id``, ``quantity``, ``system``,
  ``template``, ``parser``, ``assumes``);
- ``data/<quantity>/NNNN.jsonl``: active (believed correct) shards; line 1 is the header
  ``{"format":1,"quantity":...}``, every further line is a row with the key fields and ``out``;
- ``retracted/<quantity>/NNNN.jsonl``: retracted shards, moved there unchanged;
- ``provenance/<quantity>.jsonl``: append-only events.

Events (all have ``event``, ``date``, ``host``, ``tool_commit``):

- ``produced`` / ``confirmed`` / ``disagreed``: ``shard``, ``sha256``, ``recipe``, ``recipe_sha256``,
  ``system_version``, ``assumes``; ``disagreed`` also ``mismatches`` (list of keys);
- ``retracted``: ``shard``, ``sha256``, ``reason``, optional ``superseded_by``;
- ``inherited``: ``shard``, ``sha256``, ``source``, ``source_sha256``, ``excluded`` (list of keys):
  every row of ``shard`` whose key occurs in ``source`` and is not excluded is byte-identical to the
  source row and inherits the source's support;
- ``retracted_recipe``: ``recipe``, optional ``system_version``, ``reason``: events of that recipe
  (and system version, if given) no longer count as support.

Status is derived from the log, never stored.
"""
