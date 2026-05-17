/**
 * crawfish-web — marketing only. No auth, no app surfaces.
 *
 * Signed-in collaboration (org canvas online, sessions sharing, team
 * management, onboarding wizard, invites, billing) lives in the separate
 * crawfish-platform/ project. Every CTA on the marketing site that
 * requires an account links out to crawfish-platform.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Index } from "./pages/Index";
import "@crawfish/ui/tokens/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
