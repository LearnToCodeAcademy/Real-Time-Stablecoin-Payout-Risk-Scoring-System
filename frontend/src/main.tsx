import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const defaultView = document.body.dataset.defaultView || new URLSearchParams(location.search).get("view") || "command";

createRoot(document.getElementById("root")!).render(<App initialView={defaultView} />);
