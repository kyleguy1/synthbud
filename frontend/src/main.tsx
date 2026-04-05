import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { initializeRuntimeConfig } from "./lib/runtime";
import { FavoritesProvider } from "./state/FavoritesContext";
import { PlayerProvider } from "./state/PlayerContext";
import "./styles.css";

function renderApp() {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <BrowserRouter>
        <FavoritesProvider>
          <PlayerProvider>
            <App />
          </PlayerProvider>
        </FavoritesProvider>
      </BrowserRouter>
    </React.StrictMode>
  );
}

void initializeRuntimeConfig().finally(renderApp);
