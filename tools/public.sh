#!/bin/bash
# file generated with AI assistance: Claude Code - 2026-10-26 00:40:00 UTC
#
# Builds the public snapshot for GitHub: one commit on the branch master
# (PUBLIC_BRANCH) whose tree is the tree of <ref> (default HEAD) without
# the paths in tools/public-exclude. master carries no internal history:
# its first commit has no parent, every later one has the previous master
# commit as its only parent, so each publication is one commit.
#
#   tools/public.sh [<ref>]            # or: make public
#   git push github master             # after checking the snapshot
#
# Environment:
#   PUBLIC_BRANCH     branch to write (default master)
#   PUBLIC_MESSAGE    commit message (default "Snapshot <date>")
#   PUBLIC_NAME       author and committer name (default git user.name)
#   PUBLIC_EMAIL      author and committer e-mail (default the GitHub
#                     noreply address of schmunk42), so no work address
#                     ends up in the public history
#
# The script refuses a snapshot in which the pattern of
# tools/public-forbidden still matches (internal hosts and project paths;
# the check is skipped where that file is missing), and does nothing
# when the tree is unchanged.
# It only writes refs/heads/<branch>; the working tree is not touched.
set -eu

EXCLUDE_FILE="tools/public-exclude"
FORBIDDEN_FILE="tools/public-forbidden"
INDEX=""

die() {
	echo "public.sh: $*" >&2
	exit 1
}

# Reads the exclude file without comments and blank lines.
excluded_paths() {
	sed -e 's/#.*//' -e 's/[[:space:]]*$//' "$EXCLUDE_FILE" | grep -v '^$'
}

main() {
	local ref="${1:-HEAD}" branch="${PUBLIC_BRANCH:-master}"
	local tree parent="" commit found path
	cd "$(git rev-parse --show-toplevel)"
	git rev-parse --verify --quiet "$ref^{commit}" >/dev/null \
		|| die "$ref is not a commit"
	[ -f "$EXCLUDE_FILE" ] || die "$EXCLUDE_FILE not found"

	# a separate index, so the checkout's own index stays as it is
	INDEX="$(mktemp)"
	trap 'rm -f "$INDEX"' EXIT
	GIT_INDEX_FILE="$INDEX" git read-tree "$ref"
	excluded_paths | while IFS= read -r path; do
		GIT_INDEX_FILE="$INDEX" git rm -r -q --cached --ignore-unmatch \
			-- "$path" >/dev/null
	done
	tree="$(GIT_INDEX_FILE="$INDEX" git write-tree)"

	if [ -f "$FORBIDDEN_FILE" ]; then
		found="$(git grep -I -l -i -E \
			"$(sed -e '/^#/d' -e '/^$/d' "$FORBIDDEN_FILE")" "$tree" -- . \
			|| true)"
		[ -z "$found" ] || die "internal references left in:
$found"
	fi

	if git rev-parse --verify --quiet "refs/heads/$branch" >/dev/null; then
		parent="$(git rev-parse "refs/heads/$branch")"
		if [ "$(git rev-parse "$parent^{tree}")" = "$tree" ]; then
			echo "public.sh: $branch already has this tree, nothing to do"
			return 0
		fi
	fi
	commit="$(
		GIT_AUTHOR_NAME="${PUBLIC_NAME:-$(git config user.name)}" \
		GIT_COMMITTER_NAME="${PUBLIC_NAME:-$(git config user.name)}" \
		GIT_AUTHOR_EMAIL="${PUBLIC_EMAIL:-schmunk42@users.noreply.github.com}" \
		GIT_COMMITTER_EMAIL="${PUBLIC_EMAIL:-schmunk42@users.noreply.github.com}" \
		git commit-tree "$tree" ${parent:+-p "$parent"} \
			-m "${PUBLIC_MESSAGE:-Snapshot $(date '+%Y-%m-%d')}"
	)"
	git update-ref "refs/heads/$branch" "$commit" ${parent:+"$parent"}
	echo "public.sh: $branch at $(git rev-parse --short "$commit")" \
		"($(git ls-tree -r "$tree" | wc -l | tr -d ' ') files," \
		"from $(git rev-parse --short "$ref"))"
}

main "$@"
