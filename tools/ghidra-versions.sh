#!/usr/bin/env bash
# Pick the Ghidra releases to build against, for the release workflows. Writes to $GITHUB_OUTPUT:
#   matrix   JSON list of {version, url, sha256}: the three newest Ghidra releases, or REQUESTED
#   proceed  false when CHECK_NEW is set and REPO already has a release for the newest Ghidra
#   tag      release tag to create for a new Ghidra version (TAG_PREFIX + "ghidra-" + version)
#
# Environment: GH_TOKEN, REPO (owner/name), REQUESTED (space-separated versions, optional),
#   CHECK_NEW (true for the weekly check), TAG_PREFIX (e.g. "ghidra-rare-" in forks).
set -euo pipefail
OUT=${GITHUB_OUTPUT:-/dev/stdout}

gh api 'repos/NationalSecurityAgency/ghidra/releases?per_page=50' > ghidra-releases.json
matrix=$(jq -c --arg want "${REQUESTED:-}" '
	[ .[] | select((.draft or .prerelease) | not)
	  | (.tag_name | sub("^Ghidra_"; "") | sub("_build$"; "")) as $version
	  | .assets[] | select(.name | test("^ghidra_.*_PUBLIC_[0-9]+\\.zip$"))
	  | { version: $version, url: .browser_download_url,
	      sha256: ((.digest // "") | sub("^sha256:"; "")) } ]
	| if $want == "" then .[:3]
	  else map(select(.version as $v | $want | split(" ") | index($v))) end' ghidra-releases.json)
echo "$matrix" | jq .
if [[ $(echo "$matrix" | jq length) -eq 0 ]]; then
	echo "::error::No Ghidra release matches '${REQUESTED:-}'"
	exit 1
fi

proceed=true
tag=
if [[ ${CHECK_NEW:-false} == true ]]; then
	newest=$(echo "$matrix" | jq -r '.[0].version')
	assets=$(gh api --paginate "repos/$REPO/releases?per_page=100" -q '.[].assets[].name')
	if grep -q "^ghidra_${newest}_PUBLIC_" <<<"$assets"; then
		echo "A release of $REPO already has builds for Ghidra $newest; nothing to do."
		proceed=false
	else
		tag="${TAG_PREFIX:-}ghidra-${newest}"
		echo "No release of $REPO has builds for Ghidra $newest yet; releasing $tag."
	fi
fi
{
	echo "matrix=$matrix"
	echo "proceed=$proceed"
	echo "tag=$tag"
} >> "$OUT"
