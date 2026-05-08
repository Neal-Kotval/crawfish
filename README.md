# Crawfish

> **The token observability layer for Claude Code, plus a family of MCP optimizers built around it.**

This is the umbrella repo. The actual code lives in two submodules:

| Submodule | What it is | Status |
|---|---|---|
| **[crawfish-opt](./crawfish-opt)** | Optimizer line — MCP servers that reduce tokens for specific workloads (browser today, codebase / logs next). | v0.2 shipped |
| **[crawfish-lens](./crawfish-lens)** | Local observability — reads `~/.claude/projects` JSONL transcripts and reports where tokens went. | M0 shipped |

For the full product story, see [crawfish-lens/PRODUCT.md](./crawfish-lens/PRODUCT.md). For why these are separate repos, see [crawfish-lens/docs/relationship-to-crawfish.md](./crawfish-lens/docs/relationship-to-crawfish.md).

## Cloning

```bash
git clone --recurse-submodules https://github.com/Neal-Kotval/crawfish.git
# or, after a plain clone:
git submodule update --init --recursive
```

## Working in a submodule

Submodules are **independent git repos**. You commit and push from inside each submodule, then bump the umbrella's pointer:

```bash
# Edit code in a submodule
cd crawfish-opt
# ... edits ...
git commit -am "..."
git push                       # to the submodule's own remote

# Back in the umbrella, record the new submodule SHA
cd ..
git add crawfish-opt
git commit -m "Bump crawfish-opt"
git push
```

The umbrella never contains submodule source — only a pinned commit hash per submodule. That's the whole point: `crawfish-opt` and `crawfish-lens` ship on their own cadence; the umbrella is a known-good combination.

## Updating to latest

```bash
git submodule update --remote                # fetch each submodule's tracked branch
git submodule update --remote crawfish-lens  # just one
```

## Layout

```
crawfish/                       # this umbrella repo
├── .gitmodules                 # submodule pointers
├── README.md                   # you are here
├── crawfish-opt/               # → github.com/Neal-Kotval/crawfish (will rename → crawfish-opt)
└── crawfish-lens/              # → github.com/Neal-Kotval/crawfish-lens (TBD)
```

## TODO before pushing the umbrella publicly

- [ ] Rename the GitHub repo `Neal-Kotval/crawfish` → `Neal-Kotval/crawfish-opt`, then update the URL in `.gitmodules` and run `git submodule sync`.
- [ ] Create `Neal-Kotval/crawfish-lens` on GitHub, push, then `git submodule sync` again.
- [ ] Decide whether the umbrella itself wants a public name (e.g., `crawfish-platform`) or stays as `crawfish` — currently the optimizer occupies the `crawfish` name.

## License

MIT. See each submodule for its own LICENSE.
