# GitHub CLI fallback

Use these commands only when the active harness has no usable GitHub tooling.

## Inspect the PR

```bash
gh pr view <pr> --json number,url,state,mergedAt,closedAt,headRefName,headRefOid,mergeable,mergeStateStatus,reviewDecision
gh pr checks <pr> --json name,state,bucket,link,workflow,event,startedAt,completedAt
gh api repos/<owner>/<repo>/pulls/<pr>/comments?per_page=100
gh api graphql -f query='<review threads query>' -F owner=<owner> -F repo=<repo> -F pr=<pr>
```

## Diagnose and retry CI

```bash
gh run view <run-id> --json jobs,name,workflowName,conclusion,status,url,headSha
gh api repos/<owner>/<repo>/actions/runs/<run-id>/jobs -X GET -f per_page=100
gh run rerun <run-id> --failed
```

## Reply and resolve

```bash
gh pr comment <pr> --body "[agent]: <response>"
gh api repos/<owner>/<repo>/pulls/<pr>/comments/<comment-id>/replies -X POST -f body="[agent]: <response>"
gh api graphql -f query='<resolveReviewThread mutation>' -F threadId=<thread-id>
```

Use published comments and unresolved review threads as the source of truth. `gh pr checks --watch` can watch checks, but it does not replace fresh comment and review-thread reads.
