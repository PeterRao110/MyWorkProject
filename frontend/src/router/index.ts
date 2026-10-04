import { createRouter, createWebHistory } from "vue-router";
import AppLayout from "@/layouts/AppLayout.vue";
import Instrument from "@/pages/Instrument.vue";
import Market from "@/pages/Market.vue";
import Settings from "@/pages/Settings.vue";
import Sync from "@/pages/Sync.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", redirect: "/market" },
        { path: "market", name: "market", component: Market },
        { path: "research", name: "research", component: Instrument },
        { path: "instrument/:code", name: "instrument", component: Instrument },
        { path: "sync", name: "sync", component: Sync },
        { path: "settings", name: "settings", component: Settings },
      ],
    },
  ],
});
