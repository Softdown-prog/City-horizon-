# City Horizon — Parallel Git workflow

This repository is frequently edited by multiple ChatGPT chats, agents, GitHub Actions jobs, and worker-pool jobs at the same time. The integration model must preserve every already-landed change on `main`.

## Non-negotiable rules

1. `main` is an integration branch. AI agents and normal development tasks do not commit directly to it.
2. Every chat/task gets its own branch created from the current `main`, for example `work/<area>/<short-task>-<date-or-id>`.
3. One branch should own one logical task. Worker jobs may run in parallel, but they must not share a mutable checkout or race to rewrite the same source path.
4. Before changing an existing file, read the version on the task branch. Before integration, fetch the latest `main` and reconcile it into the task branch.
5. Changes reach `main` through a pull request. Never move `main` with a forced ref update, reset, or force-push.
6. If `main` changed while a task was running, preserve those newer commits. Rebase the task branch on current `main` or merge current `main` into the task branch, resolve conflicts there, rerun focused validation, then merge the PR.
7. A conflict is a coordination signal, not permission to choose the task branch wholesale. Resolve from the current `main` plus the intentional task delta.
8. Do not replace an entire file from a stale snapshot when only a localized edit is required.
9. Generated visual assets may be produced concurrently as artifacts. Promotion into canonical runtime paths is an integration operation and must be serialized if two jobs can touch the same files.
10. GitHub Actions that write back to `main` must update from `origin/main` immediately before pushing and must use the shared concurrency group `city-horizon-main-writer` when practical. New write-back workflows must not introduce independent writer groups.

## Recommended task flow

```text
latest main
   |
   +-- work/chat-a/terrain -------- PR A --\
   +-- work/chat-b/pirate-ship ---- PR B ---+--> main
   +-- work/chat-c/rail ------------ PR C --/

Workers inside each task can run in parallel. Only integration is serialized.
```

### Start a task

```bash
git fetch origin main
git switch -c work/<area>/<task> origin/main
```

### Before opening or merging the PR

```bash
git fetch origin main
git rebase origin/main
# resolve any conflict preserving current main + this task's intended delta
git push --force-with-lease origin HEAD   # task branch only; never main
```

`--force-with-lease` is acceptable only for the isolated task branch after a rebase. It is never acceptable for `main`.

## Worker-pool rule

Parallel workers are encouraged for independent work such as directions, frames, validation, compilation, visual proofs, or distinct assets. They should produce outputs/artifacts independently. A coordinator step then promotes approved results. Do not have four workers independently rewrite the same manifest, catalog, workflow, or runtime definition.

For a four-direction asset, for example:

```text
worker SOUTH --\
worker EAST ----+--> artifacts --> validation/coordinator --> task branch --> PR --> main
worker WEST ----+
worker NORTH ---/
```

This preserves parallelism without turning `main` into shared mutable worker storage.

## Emergency rule

If a task discovers that its base is stale, do not attempt to "put main back" by resetting or force-pushing. Reconcile on the task branch. If a commit already landed incorrectly, restore only the missing change with a new forward commit or a normal revert/cherry-pick strategy; do not rewrite published `main` history.
