/**
 * crawfish-platform — signed-in collaboration web app.
 *
 * Mirrors crawfish-dash's IA (Canvas/Board/Sessions/Knowledge/Diagnoses)
 * but for online collaboration: multiple humans in the same org canvas
 * in real time, sessions sharable by permalink, team admin & billing.
 *
 * Routes:
 *   /signin/*, /signup/*      — auth (Clerk path-based routing or dev façade)
 *   /onboarding/:step?        — 21-step founder onboarding flow (unauth)
 *   /                         — org picker (signed-in landing, gated)
 *   /orgs/:org/canvas         — online org canvas (multi-cursor)
 *   /orgs/:org/board          — board
 *   /orgs/:org/sessions       — sessions list (sharable)
 *   /orgs/:org/team           — invites + roles + ACL
 *   /orgs/:org/billing        — billing
 *   /orgs/:org/settings       — org settings
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";
import { Shell } from "./Shell";
import { Auth } from "./pages/Auth";
import { OrgPicker } from "./pages/OrgPicker";
import { OnboardingFlow } from "./onboarding/OnboardingFlow";
import { OrgRoute } from "./pages/OrgRoute";
import { LinkRedeem } from "./pages/Link";
import { InviteAccept } from "./pages/InviteAccept";
import { CLERK_ENABLED, CLERK_KEY } from "./lib/clerk";
import { RequireAuth } from "./lib/useAuth";
import "@crawfish/ui/tokens/globals.css";

const tree = (
  <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    <Routes>
      <Route path="/signin/*" element={<Auth mode="signin" />} />
      <Route path="/signup/*" element={<Auth mode="signup" />} />

      <Route path="/onboarding"        element={<OnboardingFlow />} />
      <Route path="/onboarding/:step"  element={<OnboardingFlow />} />

      <Route path="/link/:code" element={<RequireAuth><LinkRedeem /></RequireAuth>} />

      {/* Invites: rendered OUTSIDE RequireAuth so unsigned visitors can preview. */}
      <Route path="/invites/:code" element={<InviteAccept />} />

      <Route element={<RequireAuth><Shell /></RequireAuth>}>
        <Route path="/" element={<OrgPicker />} />
        <Route path="/orgs/:org/:tab" element={<OrgRoute />} />
        <Route path="/orgs/:org"      element={<Navigate to="canvas" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </BrowserRouter>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {CLERK_ENABLED ? (
      <ClerkProvider publishableKey={CLERK_KEY!} afterSignOutUrl="/">
        {tree}
      </ClerkProvider>
    ) : (
      tree
    )}
  </React.StrictMode>,
);
