import test from "node:test";
import assert from "node:assert/strict";
import { applyOverlay, applyOverlays } from "../src/templates/apply.js";
const baseDevShop = {
    slug: "dev-shop",
    name: "Dev Shop",
    description: "Base",
    architecture: "flat",
    members: [
        { id: "pm", kind: "agent", role: "PM", name: "Alex" },
        { id: "fe-eng", kind: "agent", role: "FE", name: "Jordan" },
    ],
    crons: [
        {
            id: "backlog-groom",
            cron: "0 8 * * 1",
            member_id: "pm",
            prompt: "groom",
            output_to: "board",
            enabled: true,
            last_run: null,
        },
    ],
};
const consumerMobile = {
    slug: "consumer-mobile",
    name: "Consumer Mobile",
    description: "iOS+Android reviewers",
    add_members: [
        { id: "ios-review", kind: "agent", role: "iOS Reviewer", name: "Coast" },
        { id: "android-review", kind: "agent", role: "Android Reviewer", name: "Pine" },
    ],
};
const b2bSaas = {
    slug: "b2b-saas",
    name: "B2B SaaS",
    description: "CS + SE",
    add_members: [
        { id: "cs-agent", kind: "agent", role: "CS", name: "Briar" },
    ],
    add_crons: [
        {
            id: "churn-watch",
            cron: "0 9 * * 1",
            member_id: "cs-agent",
            prompt: "watch",
            output_to: "board",
            enabled: true,
            last_run: null,
        },
    ],
};
test("applyOverlay appends members without renaming", () => {
    const merged = applyOverlay(baseDevShop, consumerMobile);
    assert.equal(merged.members.length, 4);
    assert.deepEqual(merged.members.map((m) => m.id), ["pm", "fe-eng", "ios-review", "android-review"]);
    // Base is untouched.
    assert.equal(baseDevShop.members.length, 2);
});
test("applyOverlay appends crons + knowledge_sources", () => {
    const merged = applyOverlay(baseDevShop, b2bSaas);
    assert.equal(merged.crons?.length, 2);
    assert.deepEqual(merged.crons?.map((c) => c.id).sort(), ["backlog-groom", "churn-watch"]);
});
test("applyOverlay rejects member id collisions", () => {
    const bad = {
        slug: "bad",
        name: "Bad",
        description: "x",
        add_members: [{ id: "pm", kind: "agent", role: "Other", name: "Conflict" }],
    };
    assert.throws(() => applyOverlay(baseDevShop, bad), /collides/);
});
test("applyOverlays composes in order", () => {
    const merged = applyOverlays(baseDevShop, [consumerMobile, b2bSaas]);
    assert.deepEqual(merged.members.map((m) => m.id), ["pm", "fe-eng", "ios-review", "android-review", "cs-agent"]);
});
