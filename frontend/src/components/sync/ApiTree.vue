<script setup lang="ts">
import type { CatalogNode } from "@/data/tushareCatalog";

defineProps<{
  nodes: CatalogNode[];
  depth: number;
  expanded: Record<string, boolean>;
  activeId: string;
}>();

const emit = defineEmits<{
  toggle: [id: string];
  select: [id: string];
}>();
</script>

<template>
  <div v-for="node in nodes" :key="node.id">
    <button
      v-if="node.children?.length"
      type="button"
      class="tree-item branch"
      :style="{ paddingLeft: `${10 + depth * 16}px` }"
      @click="emit('toggle', node.id)"
    >
      <svg class="chevron" :class="{ open: expanded[node.id] }" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M4 2.5 8 6 4 9.5" />
      </svg>
      <span>{{ node.title }}</span>
    </button>
    <button
      v-else
      type="button"
      class="tree-item"
      :class="{ active: activeId === node.id }"
      :style="{ paddingLeft: `${28 + depth * 16}px` }"
      @click="emit('select', node.id)"
    >
      {{ node.title }}
    </button>
    <ApiTree
      v-if="node.children?.length && expanded[node.id]"
      :nodes="node.children"
      :depth="depth + 1"
      :expanded="expanded"
      :active-id="activeId"
      @toggle="emit('toggle', $event)"
      @select="emit('select', $event)"
    />
  </div>
</template>
