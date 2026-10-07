<script setup lang="ts">
import { reactive, ref } from "vue";
import {
  CRON_PRESETS,
  createScheduleGroup,
  updateScheduleGroup,
  type ScheduleGroup,
  type ScheduleGroupInput,
} from "@/services/schedule";

const props = defineProps<{
  group?: ScheduleGroup | null;
}>();

const emit = defineEmits<{
  close: [];
  saved: [];
}>();

const saving = ref(false);
const error = ref("");
const preset = ref(initialPreset(props.group));
const form = reactive({
  name: props.group?.name ?? "",
  cron: props.group?.cron || "0 8 * * *",
  followPrevious: props.group?.followPrevious ?? false,
  stopOnFailure: props.group?.stopOnFailure ?? true,
  enabled: props.group?.enabled ?? true,
});

function initialPreset(group?: ScheduleGroup | null) {
  if (!group) return "0 8 * * *";
  if (!group.cron) return "none";
  return CRON_PRESETS.some((item) => item.value === group.cron) ? group.cron : "custom";
}

async function save() {
  error.value = "";
  if (!form.name.trim()) {
    error.value = "请填写任务组名称";
    return;
  }
  const cron = preset.value === "none" ? "" : preset.value === "custom" ? form.cron.trim() : preset.value;
  if (!cron && !form.followPrevious) {
    error.value = "请填写执行频率，或勾选上一组成功后接着运行";
    return;
  }
  const payload: ScheduleGroupInput = {
    name: form.name.trim(),
    cron,
    followPrevious: form.followPrevious,
    stopOnFailure: form.stopOnFailure,
    enabled: form.enabled,
  };
  saving.value = true;
  try {
    if (props.group) {
      await updateScheduleGroup(props.group.id, payload);
    } else {
      await createScheduleGroup(payload);
    }
    emit("saved");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "保存失败";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-label="任务组">
      <header>
        <strong>{{ group ? "编辑任务组" : "新建任务组" }}</strong>
        <button type="button" class="icon-btn" aria-label="关闭" @click="emit('close')">×</button>
      </header>
      <div class="form-grid" style="margin-top: 14px">
        <label class="wide">
          <span>任务组名称</span>
          <input v-model="form.name" placeholder="例如：开盘准备" />
        </label>
        <label>
          <span>执行频率</span>
          <select v-model="preset">
            <option v-for="item in CRON_PRESETS" :key="item.value" :value="item.value">{{ item.label }}</option>
            <option value="custom">自定义</option>
            <option value="none">不单独定时</option>
          </select>
        </label>
        <label v-if="preset === 'custom'">
          <span>cron 表达式（分 时 日 月 星期，0 或 7 表示周日）</span>
          <input v-model="form.cron" placeholder="0 8 * * *" />
        </label>
        <label class="switch">
          <input v-model="form.followPrevious" type="checkbox" />
          <span>上一组成功后接着运行</span>
        </label>
        <label class="switch">
          <input v-model="form.stopOnFailure" type="checkbox" />
          <span>组内任务失败后停止后续</span>
        </label>
        <label class="switch">
          <input v-model="form.enabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>
      <p class="hint">
        组内任务按顺序逐个执行。组与组按列表中的先后排列；勾选接续后，紧邻的上一组成功结束时会自动运行本组。
      </p>
      <p v-if="error" class="hint error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="run-btn" :disabled="saving" @click="save">
          {{ saving ? "保存中..." : "保存任务组" }}
        </button>
        <button type="button" class="ghost-btn" @click="emit('close')">取消</button>
      </div>
    </div>
  </div>
</template>
