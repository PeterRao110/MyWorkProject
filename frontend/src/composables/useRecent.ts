import { ref } from "vue";

const STORAGE_KEY = "touyan-recent";

function readRecent(): string[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

const items = ref<string[]>(readRecent());

export function useRecent() {
  function push(code: string) {
    items.value = [code, ...items.value.filter((item) => item !== code)].slice(0, 8);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items.value));
  }

  return { items, push };
}
