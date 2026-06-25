# Reference

Look-up pages for the Crawfish API. Every public symbol in `crawfish.__all__` is covered
here with worked examples. The [flat API list](../guide/api-reference.md) links into these
pages.

## How a page reads

Each page covers one cluster of related symbols. It opens with a short explanation, shows
a runnable example, and ends with an API reference table for every symbol. Read to
whatever depth answers your question.

Every example is deterministic. It runs on pure functions or
[`MockRuntime`](runtimes.md#mockruntime), never a live model, so the output in the
collapsible **▶ Output** blocks does not drift.

## The map

Start at the foundations and work outward.

| Group | Pages |
| --- | --- |
| **Foundations** | [Core types](core-types.md) · [Type system](type-system.md) · [Versioning & stability](versioning-and-stability.md) · [Context & budgets](context-and-budgets.md) |
| **Building pipelines** | [Output & wiring](output-and-wiring.md) · [Validation](validation.md) · [Context carry](context-carry.md) · [Definition](definition.md) · [Runtimes](runtimes.md) · [Providers](providers.md) · [Source & filter](nodes-source-filter.md) · [Aggregator](nodes-aggregator.md) · [Router & sink](nodes-router-sink.md) |
| **Running & storage** | [Run & engine](run-and-engine.md) · [Batch & execution](batch-and-execution.md) · [Persistence](persistence.md) |
| **Observability** | [Emission, inspector & visualize](emission-inspector-visualize.md) · [Anomaly](anomaly.md) · [Observer](observer.md) · [Cost, routing & cache](cost-routing-cache.md) |
| **Evaluation & tuning** | [Metrics](metrics.md) · [Evals](evals.md) · [Tuner & learning](tuner-and-learning.md) |
| **Control plane** | [Refine & verify](refine-and-verify.md) |
| **Secrets & sandboxing** | [Secrets & consent](secrets-and-consent.md) · [Secret broker](secret-broker.md) · [Sandbox & jail](sandbox-and-jail.md) |
| **Operations & tooling** | [Deploy, manage & triggers](operate.md) · [Authoring & config](authoring.md) · [Testing](testing.md) · [Claude Code export](claude-code-export.md) |
