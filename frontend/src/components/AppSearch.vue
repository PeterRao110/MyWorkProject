<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { searchInstruments } from "@/services/market";
import type { Instrument } from "@/types/market";

const route = useRoute();
const router = useRouter();
const root = ref<HTMLElement | null>(null);
const query = ref("");
const open = ref(false);
const active = ref(0);

const results = computed(() => searchInstruments(query.value));

watch(query, () => {
  active.value = 0;
  open.value = query.value.trim().length > 0;
});

watch(
  () => route.fullPath,
  () => {
    query.value = "";
    open.value = false;
  },
);

function go(item: Instrument) {
  open.value = false;
  query.value = "";
  void router.push(`/instrument/${encodeURIComponent(item.code)}`);
}

function onSubmit() {
  const picked = results.value[active.value];
  if (picked) go(picked);
}

function onKeydown(event: KeyboardEvent) {
  if (!results.value.length) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    active.value = Math.min(active.value + 1, results.value.length - 1);
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    active.value = Math.max(active.value - 1, 0);
  }
  if (event.key === "Escape") open.value = false;
}

function onPointerDown(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false;
}

function subtitle(item: Instrument) {
  if (item.assetType === "stock") return `${item.code} · 股票 · ${item.industry}`;
  return `${item.code} · 期货 · ${item.exchangeName}`;
}

onMounted(() => document.addEventListener("pointerdown", onPointerDown));
onBeforeUnmount(() => document.removeEventListener("pointerdown", onPointerDown));
</script>

<template>
  <form ref="root" class="search" @submit.prevent="onSubmit">
    <input
      v-model="query"
      type="search"
      placeholder="搜索股票、合约或品种"
      aria-label="搜索股票、合约或品种"
      @focus="open = query.trim().length > 0"
      @keydown="onKeydown"
    />
    <div v-if="open && results.length" class="results" role="listbox">
      <button
        v-for="(item, index) in results"
        :key="item.code"
        type="button"
        :class="{ active: index === active }"
        @mouseenter="active = index"
        @click="go(item)"
      >
        <span>{{ item.name }}</span>
        <small>{{ subtitle(item) }}</small>
      </button>
    </div>
  </form>
</template>
