# Demo recording script — the zero-key 5-minute wow

How to capture the above-the-fold demo for the README (`demo.gif`). The flow shows a
fresh user going from `pip install` to a running pipeline with **no API key** (the demo
runs on a mock runtime).

## What the recording should show

1. Install Crawfish.
2. `craw init` scaffolds a project.
3. `craw dev …` runs a Definition end to end and prints a typed Output — zero key.

## Setup (do this before you hit record)

Use a clean directory and a wide-but-short terminal so the GIF stays legible:

```bash
mkdir -p /tmp/crawfish-demo && cd /tmp/crawfish-demo
# Terminal ~90 cols x ~24 rows reads well in a README at full width.
```

## Recording with asciinema → GIF

```bash
# 1. Record (Ctrl-D or `exit` to stop).
asciinema rec demo.cast --cols 90 --rows 24 --idle-time-limit 2

# 2. Convert the cast to a GIF with agg (https://github.com/asciinema/agg).
agg demo.cast demo.gif

# 3. Drop it next to this file and reference it from the README.
mv demo.gif docs/assets/demo.gif
```

Prefer a pure-GIF tool? [`vhs`](https://github.com/charmbracelet/vhs) records a `.tape`
script straight to GIF and is fully reproducible — see the tape at the bottom.

## The exact commands to type during the recording

Type these at a natural pace (the `--idle-time-limit 2` above trims long pauses):

```bash
# Install the published package (zero key needed for the demo).
pip install crawfish        # TODO(maintainer): confirm the dist name is `crawfish`

# Scaffold a new project.
craw init my-app
cd my-app

# Run a Definition end to end on the mock runtime — no API key.
craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"
```

The `craw dev` call prints a typed Output: the Source fans the item out, the Definition
team runs via the mock runtime, and the result comes back typed — all locally, no key.

> Dev-tree variant (if recording from a clone instead of the published package): swap the
> install for `just deps` and run the bundled demo directly:
> `uv run craw dev demo/triage-bot -i project=acme -i "ticket_body=login is broken"`.

## Optional: a reproducible `vhs` tape

Save as `demo.tape` and run `vhs demo.tape` to regenerate `demo.gif` deterministically:

```tape
Output docs/assets/demo.gif
Set FontSize 16
Set Width 1200
Set Height 600
Set Theme "Dracula"

Type "pip install crawfish"
Enter
Sleep 2s

Type "craw init my-app && cd my-app"
Enter
Sleep 1s

Type `craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"`
Enter
Sleep 4s
```
