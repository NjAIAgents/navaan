import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/manrope";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "@fontsource/noto-serif-devanagari/600.css";
import "./styles/tokens.css";
import "./styles/themes/midnight-cinema.css";
import "./styles/themes/ivory-gold.css";
import "./styles/base.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename="/app"><App /></BrowserRouter>
  </StrictMode>,
);
