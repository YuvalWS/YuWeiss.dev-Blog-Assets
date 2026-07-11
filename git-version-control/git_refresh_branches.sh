#!/bin/bash
# Fetches remote branches and writes names (one per line) to /tmp/git_branches.txt
cd /config || exit 1
git fetch origin --prune 2>/dev/null
git branch -r --format='%(refname:short)' | sed 's|origin/||' | grep -v '^HEAD' | sort > /tmp/git_branches.txt
cat /tmp/git_branches.txt
