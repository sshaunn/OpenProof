"""The transactional promote (§10/§12a). ``snapshot`` builds the deterministic receipt
(``events.jsonl`` + ``unparsed.jsonl`` + ``manifest.yml`` + ``ledgerStateHash``); ``promote``
moves a staged candidate into the tracked ``committed/<ledgerStateHash>/`` surface."""
