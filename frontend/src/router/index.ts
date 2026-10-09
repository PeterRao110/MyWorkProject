import { createRouter, createWebHistory } from "vue-router";
import AppLayout from "@/layouts/AppLayout.vue";
import Instrument from "@/pages/Instrument.vue";
import Login from "@/pages/Login.vue";
import Market from "@/pages/Market.vue";
import Schedule from "@/pages/Schedule.vue";
import Settings from "@/pages/Settings.vue";
import Sync from "@/pages/Sync.vue";
import { hasSession } from "@/services/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: Login },
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", redirect: "/market" },
        { path: "market", name: "market", component: Market },
        { path: "research", name: "research", component: Instrument },
        { path: "instrument/:code", name: "instrument", component: Instrument },
        { path: "sync", name: "sync", component: Sync },
        { path: "schedule", name: "schedule", component: Schedule },
        { path: "settings", name: "settings", component: Settings },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  if (to.name === "login") return true;
  if (await hasSession()) return true;
  return { name: "login" };
});
