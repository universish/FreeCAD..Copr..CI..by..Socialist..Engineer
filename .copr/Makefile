# Copr must receive the prebuilt, security-scanned SRPM from GitHub Actions.
# Do not download or package upstream sources on a Copr builder.

srpm:
	@echo "Direct Copr source builds are disabled; submit a verified SRPM from GitHub Actions." >&2
	@exit 1

.PHONY: srpm
