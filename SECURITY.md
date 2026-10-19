# Credential handling

Do not post Earthdata or GitHub tokens, passwords, private keys, or signed access
URLs in this repository, issues, commits, or reports. NASA access uses a hidden
terminal prompt or a securely configured environment variable. Raw scientific
inputs and common credential paths are ignored by Git.

Before a commit, run `python scripts/check_publication.py --staged`. CI scans
tracked files with the same bounded checks. Pattern scanning is a useful check,
not a guarantee against every possible encoding or credential type.

If a credential has been exposed, revoke it at its provider immediately and use
a replacement. Removing a file from the current tree does not remove earlier
Git objects, external caches, or chat messages. Report suspected exposures to the
repository owner without repeating the credential in a public issue.
