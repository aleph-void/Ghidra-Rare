# Instructions for agents

## Upstream GitHub repositories

Never open a duplicate issue or pull request on an upstream repository. Before creating one:

1. Search the repository's existing issues and pull requests, open and closed, for the same subject
   (for example `gh issue list -R <owner>/<repo> --state all --search "<keywords>"` and
   `gh pr list -R <owner>/<repo> --state all --search "<keywords>"`).
2. Check the "License requests" table in `community/CANDIDATES.md`, which records every request
   Ghidra-Rare has already made.

If a matching issue or pull request exists, comment on it (or leave it alone) instead of opening a new
one. Record any new request in `community/CANDIDATES.md`.
