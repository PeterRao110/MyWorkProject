import { createApp } from "vue";
import App from "./App.vue";
import { markSignedOut } from "./services/auth";
import { router } from "./router";
import "./styles/index.css";

const rawFetch = window.fetch.bind(window);
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const response = await rawFetch(input, init);
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (response.status === 401 && url.includes("/api/") && !url.includes("/api/auth/")) {
    markSignedOut();
    if (router.currentRoute.value.name !== "login") await router.replace({ name: "login" });
  }
  return response;
};

createApp(App).use(router).mount("#app");
