import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import TapTapChat from "./TapTapChat";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: "100%", maxWidth: 860, height: "100vh" }}>
        <TapTapChat apiUrl="/chat" faculty="Faculty" />
      </div>
    </div>
  </StrictMode>
);
