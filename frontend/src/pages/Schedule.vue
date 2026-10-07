<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import GroupDialog from "@/components/schedule/GroupDialog.vue";
import JobDialog, { type JobPrefill } from "@/components/schedule/JobDialog.vue";
import RunDetailDialog from "@/components/schedule/RunDetailDialog.vue";
import RunStateTable from "@/components/schedule/RunStateTable.vue";
import {
  deleteScheduleGroup,
  deleteScheduleJob,
  listGroupRunCalls,
  listScheduleGroupRuns,
  listScheduleGroups,
  listScheduleJobs,
  listScheduleRunStates,
  listScheduleRuns,
  reorderScheduleGroups,
  reorderScheduleJobs,
  retryScheduleRun,
  runScheduleGroup,
  runScheduleJob,
  toggleScheduleGroup,
  toggleScheduleJob,
  type ScheduleGroup,
  type ScheduleGroupRun,
  type ScheduleJob,
  type ScheduleRun,
  type ScheduleRunState,
} from "@/services/schedule";

const route = useRoute();
const router = useRouter();
const groups = ref<ScheduleGroup[]>([]);
const jobs = ref<ScheduleJob[]>([]);
const runs = ref<ScheduleRun[]>([]);
const groupRuns = ref<ScheduleGroupRun[]>([]);
const runDetail = ref<{
  title: string;
  summary: ScheduleGroupRun | null;
  calls: ScheduleRun[];
  loading: boolean;
  error: string;
} | null>(null);
const runStates = ref<ScheduleRunState[]>([]);
const selectedKind = ref<"group" | "job" | "">("");
const selectedId = ref<number | null>(null);
const dialogOpen = ref(false);
const groupDialogOpen = ref(false);
const editJob = ref<ScheduleJob | null>(null);
const editGroup = ref<ScheduleGroup | null>(null);
const prefill = ref<JobPrefill | null>(null);
const initialGroupId = ref<number | null>(null);
const loadError = ref("");
const refreshingRuns = ref(false);
const pageTab = ref<"config" | "status">("status");
const runningJobIds = ref<number[]>([]);
let pageAlive = true;

const sortedGroups = computed(() =>
  [...groups.value].sort((a, b) => a.sortOrder - b.sortOrder || a.id - b.id),
);
const standaloneJobs = computed(() => jobs.value.filter((job) => job.groupId == null));
const selectedGroup = computed(
  () => groups.value.find((group) => selectedKind.value === "group" && group.id === selectedId.value) ?? null,
);
const selectedJob = computed(
  () => jobs.value.find((job) => selectedKind.value === "job" && job.id === selectedId.value) ?? null,
);
const groupMembers = computed(() => (selectedGroup.value ? membersOf(selectedGroup.value.id) : []));
const selectedGroupIndex = computed(() =>
  sortedGroups.value.findIndex((group) => group.id === selectedGroup.value?.id),
);

let timer: number | undefined;

onMounted(async () => {
  await refresh();
  timer = window.setInterval(() => void refresh(true), 15000);
  if (route.query.create === "1") {
    prefill.value = {
      docId: typeof route.query.docId === "string" ? route.query.docId : undefined,
      source: route.query.source === "rds" ? "rds" : "promax",
      params: parseParamsQuery(route.query.params),
      fields: typeof route.query.fields === "string" ? route.query.fields.split(",").filter(Boolean) : undefined,
    };
    editJob.value = null;
    initialGroupId.value = null;
    dialogOpen.value = true;
    router.replace({ name: "schedule" });
  }
});

onUnmounted(() => {
  pageAlive = false;
  if (timer !== undefined) window.clearInterval(timer);
});

function parseParamsQuery(raw: unknown) {
  if (typeof raw !== "string" || !raw) return undefined;
  try {
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    return undefined;
  }
}

function membersOf(groupId: number) {
  return jobs.value
    .filter((job) => job.groupId === groupId)
    .sort((a, b) => a.sortOrder - b.sortOrder || a.id - b.id);
}

function earlierGroup(group: ScheduleGroup) {
  return sortedGroups.value
    .filter(
      (item) =>
        item.enabled &&
        item.id !== group.id &&
        (item.sortOrder < group.sortOrder || (item.sortOrder === group.sortOrder && item.id < group.id)),
    )
    .at(-1);
}

function groupNextText(group: ScheduleGroup, seen = new Set<number>()): string {
  if (group.nextRunAt) return group.nextRunAt;
  if (!group.followPrevious || seen.has(group.id)) return group.followPrevious ? "随上一组" : "-";
  seen.add(group.id);
  const prev = earlierGroup(group);
  if (!prev) return "随上一组";
  const text = groupNextText(prev, seen);
  return text === "-" ? "随上一组" : text;
}

function jobNextText(job: ScheduleJob) {
  if (job.groupId == null) return job.nextRunAt || "-";
  const group = groups.value.find((item) => item.id === job.groupId);
  return group ? groupNextText(group) : job.nextRunAt || "随任务组";
}

function groupName(groupId: number | null) {
  if (groupId == null) return "";
  return groups.value.find((group) => group.id === groupId)?.name || "任务组";
}

function groupScheduleText(group: ScheduleGroup) {
  const parts: string[] = [];
  if (group.cron) parts.push(group.cron);
  if (group.followPrevious) parts.push("上一组成功后接续");
  return parts.join(" · ") || "未设置调度";
}

async function refresh(silent = false) {
  try {
    const [nextJobs, nextGroups, nextStates] = await Promise.all([
      listScheduleJobs(),
      listScheduleGroups(),
      listScheduleRunStates(),
    ]);
    jobs.value = nextJobs;
    groups.value = nextGroups;
    runStates.value = nextStates;
    loadError.value = "";
    const selectedGone =
      (selectedKind.value === "group" && !nextGroups.some((group) => group.id === selectedId.value)) ||
      (selectedKind.value === "job" && !nextJobs.some((job) => job.id === selectedId.value));
    if (selectedGone) {
      selectedKind.value = "";
      selectedId.value = null;
    }
    if (selectedId.value === null) {
      if (nextGroups.length) {
        selectedKind.value = "group";
        selectedId.value = [...nextGroups].sort((a, b) => a.sortOrder - b.sortOrder || a.id - b.id)[0].id;
      } else if (nextJobs.length) {
        selectedKind.value = "job";
        selectedId.value = nextJobs[0].id;
      }
    }
    await loadSelection();
  } catch (error) {
    if (!silent) loadError.value = error instanceof Error ? error.message : "读取调度数据失败";
  }
}

async function loadSelection() {
  if (selectedKind.value === "group" && selectedId.value !== null) {
    groupRuns.value = await listScheduleGroupRuns(selectedId.value);
    runs.value = [];
    return;
  }
  if (selectedKind.value === "job" && selectedId.value !== null) {
    runs.value = await listScheduleRuns(selectedId.value);
    groupRuns.value = [];
  }
}

function selectGroup(group: ScheduleGroup) {
  selectedKind.value = "group";
  selectedId.value = group.id;
  void loadSelection();
}

function selectJob(job: ScheduleJob) {
  selectedKind.value = "job";
  selectedId.value = job.id;
  void loadSelection();
}

function selectJobById(jobId: number) {
  const job = jobs.value.find((item) => item.id === jobId);
  if (!job) return;
  pageTab.value = "config";
  selectJob(job);
}

function onStateSaved() {
  show("已保存运行状态", true);
  void refresh(true);
}

async function toggleJob(job: ScheduleJob, event: Event) {
  const enabled = (event.target as HTMLInputElement).checked;
  try {
    await toggleScheduleJob(job.id, enabled);
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "操作失败", false);
  }
}

async function toggleGroup(group: ScheduleGroup, event: Event) {
  const enabled = (event.target as HTMLInputElement).checked;
  try {
    await toggleScheduleGroup(group.id, enabled);
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "操作失败", false);
  }
}

async function runJob(job: ScheduleJob) {
  try {
    await runScheduleJob(job.id);
    window.setTimeout(() => void refresh(true), 2000);
  } catch (error) {
    show(error instanceof Error ? error.message : "触发失败", false);
  }
}

async function runGroup(group: ScheduleGroup, chain: boolean) {
  try {
    const text = await runScheduleGroup(group.id, chain);
    if (text !== "已触发运行") show(text, true);
    window.setTimeout(() => void refresh(true), 1500);
  } catch (error) {
    show(error instanceof Error ? error.message : "触发失败", false);
  }
}

async function removeJob(job: ScheduleJob) {
  if (!window.confirm(`确定删除任务「${job.name}」？运行记录会一起删除。`)) return;
  try {
    await deleteScheduleJob(job.id);
    if (selectedKind.value === "job" && selectedId.value === job.id) {
      selectedKind.value = "";
      selectedId.value = null;
    }
    show("已删除", true);
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "删除失败", false);
  }
}

async function removeGroup(group: ScheduleGroup) {
  if (!window.confirm(`确定删除任务组「${group.name}」？`)) return;
  try {
    await deleteScheduleGroup(group.id);
    if (selectedKind.value === "group" && selectedId.value === group.id) {
      selectedKind.value = "";
      selectedId.value = null;
    }
    show("已删除", true);
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "删除失败", false);
  }
}

async function moveGroup(group: ScheduleGroup, delta: number) {
  const list = [...sortedGroups.value];
  const index = list.findIndex((item) => item.id === group.id);
  const target = index + delta;
  if (index < 0 || target < 0 || target >= list.length) return;
  const [item] = list.splice(index, 1);
  list.splice(target, 0, item);
  try {
    await reorderScheduleGroups(list.map((entry) => entry.id));
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "调整顺序失败", false);
  }
}

function moveSelectedMember(job: ScheduleJob, delta: number) {
  if (!selectedGroup.value) return;
  void moveMember(selectedGroup.value.id, job, delta);
}

function backToGroup() {
  const group = groups.value.find((item) => item.id === selectedJob.value?.groupId);
  if (group) selectGroup(group);
}

function runSelectedJob() {
  if (!selectedJob.value) return;
  void runJob(selectedJob.value);
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitForTriggeredRun(jobId: number, baselineId: number | null) {
  const deadline = Date.now() + 30 * 60 * 1000;
  let sawRunning = false;
  while (pageAlive && Date.now() < deadline) {
    await sleep(1000);
    if (!pageAlive) return;
    try {
      const [runs, states] = await Promise.all([listScheduleRuns(jobId), listScheduleRunStates()]);
      const latest = runs[0];
      const jobRunning = states.find((item) => item.jobId === jobId)?.lastStatus === "running";
      if (jobRunning) {
        sawRunning = true;
        continue;
      }
      if (!latest) continue;
      if (baselineId !== null) {
        if (latest.id > baselineId && latest.status !== "running") return;
        continue;
      }
      if (latest.status === "running") sawRunning = true;
      if (sawRunning && latest.status !== "running") return;
    } catch {
      // 下一轮再查这次运行是否已经结束
    }
  }
}

async function runStateJob(jobId: number) {
  if (runningJobIds.value.includes(jobId)) return;
  const job = jobs.value.find((item) => item.id === jobId);
  if (!job) {
    show("任务不存在", false);
    return;
  }
  runningJobIds.value = [...runningJobIds.value, jobId];
  try {
    let baselineId: number | null = null;
    try {
      const existing = await listScheduleRuns(jobId);
      baselineId = existing[0]?.id ?? 0;
    } catch {
      baselineId = null;
    }
    await runScheduleJob(jobId);
    await waitForTriggeredRun(jobId, baselineId);
    if (!pageAlive) return;
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "触发失败", false);
  } finally {
    runningJobIds.value = runningJobIds.value.filter((id) => id !== jobId);
  }
}

async function refreshRuns() {
  if (refreshingRuns.value) return;
  refreshingRuns.value = true;
  try {
    await loadSelection();
  } catch (error) {
    show(error instanceof Error ? error.message : "刷新运行记录失败", false);
  } finally {
    refreshingRuns.value = false;
  }
}

async function moveMember(groupId: number, job: ScheduleJob, delta: number) {
  const list = [...membersOf(groupId)];
  const index = list.findIndex((item) => item.id === job.id);
  const target = index + delta;
  if (index < 0 || target < 0 || target >= list.length) return;
  const [item] = list.splice(index, 1);
  list.splice(target, 0, item);
  try {
    await reorderScheduleJobs(groupId, list.map((entry) => entry.id));
    await refresh(true);
  } catch (error) {
    show(error instanceof Error ? error.message : "调整顺序失败", false);
  }
}

const detailRequest = ref(0);

async function openStateRunDetail(jobId: number) {
  const token = ++detailRequest.value;
  const job = jobs.value.find((item) => item.id === jobId);
  runDetail.value = {
    title: job?.name || "任务",
    summary: null,
    calls: [],
    loading: true,
    error: "",
  };
  try {
    const list = await listScheduleRuns(jobId);
    if (token !== detailRequest.value) return;
    const latest = list[0];
    runDetail.value = {
      title: latest?.jobName || job?.name || "任务",
      summary: null,
      calls: latest ? [latest] : [],
      loading: false,
      error: "",
    };
  } catch (error) {
    if (token !== detailRequest.value) return;
    runDetail.value = {
      title: job?.name || "任务",
      summary: null,
      calls: [],
      loading: false,
      error: error instanceof Error ? error.message : "读取运行详情失败",
    };
  }
}

function closeRunDetail() {
  detailRequest.value += 1;
  runDetail.value = null;
}

function openJobRunDetail(run: ScheduleRun) {
  runDetail.value = {
    title: run.jobName || selectedJob.value?.name || "任务",
    summary: null,
    calls: [run],
    loading: false,
    error: "",
  };
}

async function openGroupRunDetail(run: ScheduleGroupRun) {
  runDetail.value = {
    title: selectedGroup.value?.name || "任务组",
    summary: run,
    calls: [],
    loading: true,
    error: "",
  };
  try {
    const calls = await listGroupRunCalls(run.id);
    if (!runDetail.value || runDetail.value.summary?.id !== run.id) return;
    runDetail.value = { ...runDetail.value, calls, loading: false };
  } catch (error) {
    if (!runDetail.value || runDetail.value.summary?.id !== run.id) return;
    runDetail.value = {
      ...runDetail.value,
      loading: false,
      error: error instanceof Error ? error.message : "读取运行详情失败",
    };
  }
}

async function retry(run: ScheduleRun) {
  try {
    show(await retryScheduleRun(run.id), true);
    window.setTimeout(() => void refresh(true), 2000);
  } catch (error) {
    show(error instanceof Error ? error.message : "重跑失败", false);
  }
}

function openCreate() {
  editJob.value = null;
  prefill.value = null;
  initialGroupId.value = null;
  dialogOpen.value = true;
}

function openCreateInGroup() {
  if (!selectedGroup.value) return;
  editJob.value = null;
  prefill.value = null;
  initialGroupId.value = selectedGroup.value.id;
  dialogOpen.value = true;
}

function openEditJob() {
  if (!selectedJob.value) return;
  editJob.value = selectedJob.value;
  prefill.value = null;
  initialGroupId.value = null;
  dialogOpen.value = true;
}

function openCreateGroup() {
  editGroup.value = null;
  groupDialogOpen.value = true;
}

function openEditGroup() {
  if (!selectedGroup.value) return;
  editGroup.value = selectedGroup.value;
  groupDialogOpen.value = true;
}

async function onSaved() {
  dialogOpen.value = false;
  groupDialogOpen.value = false;
  show("已保存", true);
  await refresh(true);
}

function statusText(status: string) {
  return { success: "成功", failed: "失败", running: "运行中" }[status] || "未运行";
}

function triggerText(trigger: string) {
  return { cron: "定时", manual: "手动", retry: "重跑", group: "任务组", chain: "接续" }[trigger] || trigger;
}

function duration(run: { startedAt: string; finishedAt: string }) {
  if (!run.startedAt || !run.finishedAt) return "-";
  const ms = new Date(run.finishedAt.replace(" ", "T")).getTime() - new Date(run.startedAt.replace(" ", "T")).getTime();
  if (Number.isNaN(ms) || ms < 0) return "-";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function show(_text: string, _ok: boolean) {}
</script>

<template>
  <section class="sched">
    <div class="seg sched-tabs" role="tablist" aria-label="监控调度">
      <button
        type="button"
        role="tab"
        :class="{ active: pageTab === 'status' }"
        :aria-selected="pageTab === 'status'"
        @click="pageTab = 'status'"
      >
        调度运行监控
      </button>
      <button
        type="button"
        role="tab"
        :class="{ active: pageTab === 'config' }"
        :aria-selected="pageTab === 'config'"
        @click="pageTab = 'config'"
      >
        调度配置
      </button>
    </div>

    <section v-if="pageTab === 'status'" class="sched-monitor" aria-label="调度运行监控">
      <div class="panel sched-state">
        <RunStateTable
          :rows="runStates"
          :running-ids="runningJobIds"
          @saved="onStateSaved"
          @error="show($event, false)"
          @select="selectJobById"
          @run="runStateJob"
          @detail="openStateRunDetail"
        />
      </div>
    </section>

    <div v-else class="sched-grid">
      <aside class="panel sched-list" aria-label="调度列表">
        <div class="panel-head">
          <h2>调度</h2>
          <div class="detail-ops">
            <button type="button" class="ghost-btn" @click="openCreateGroup">新建任务组</button>
            <button type="button" class="run-btn" @click="openCreate">新建任务</button>
          </div>
        </div>

        <div class="list-section">
          <strong>任务组</strong>
          <span>组间按顺序，组内也按顺序</span>
        </div>
        <div v-for="(group, index) in sortedGroups" :key="group.id" class="group-block">
          <div
            class="job-item"
            :class="{ active: selectedKind === 'group' && selectedId === group.id }"
            @click="selectGroup(group)"
          >
            <span class="seq-no">{{ index + 1 }}</span>
            <span class="status-dot" :class="{ enabled: group.enabled }" :title="group.enabled ? '已启用' : '未启用'"></span>
            <div class="job-main">
              <strong>{{ group.name }}<span v-if="group.lastStatus === 'failed'" class="name-failed">失败</span></strong>
              <small>{{ groupScheduleText(group) }} · {{ membersOf(group.id).length }} 个任务</small>
              <small>上次 {{ group.lastRunAt || "-" }} · 下次 {{ groupNextText(group) }}</small>
            </div>
            <div class="job-ops" @click.stop>
              <button type="button" class="text-btn" :disabled="index === 0" @click="moveGroup(group, -1)">上移</button>
              <button
                type="button"
                class="text-btn"
                :disabled="index === sortedGroups.length - 1"
                @click="moveGroup(group, 1)"
              >
                下移
              </button>
              <input
                type="checkbox"
                :checked="group.enabled"
                :aria-label="`启用任务组 ${group.name}`"
                @change="toggleGroup(group, $event)"
              />
              <button type="button" class="text-btn" @click="runGroup(group, false)">运行</button>
            </div>
          </div>
          <div
            v-for="(job, jobIndex) in membersOf(group.id)"
            :key="job.id"
            class="job-item member"
            :class="{ active: selectedKind === 'job' && selectedId === job.id }"
            @click="selectJob(job)"
          >
            <span class="seq-no">{{ jobIndex + 1 }}</span>
            <span class="status-dot" :class="{ enabled: job.enabled }" :title="job.enabled ? '已启用' : '未启用'"></span>
            <div class="job-main">
              <strong>{{ job.name }}<span v-if="job.lastStatus === 'failed'" class="name-failed">失败</span></strong>
              <small>{{ job.apiName }} · {{ job.source === "rds" ? "Tushare测试接口" : "Tushare接口" }}</small>
            </div>
          </div>
        </div>
        <p v-if="!sortedGroups.length && !loadError" class="pane-empty">还没有任务组。多个任务可以放进同一组，只配置一次调度。</p>

        <div class="list-section">
          <strong>单任务</strong>
          <span>按各自的 cron 调度</span>
        </div>
        <div
          v-for="job in standaloneJobs"
          :key="job.id"
          class="job-item"
          :class="{ active: selectedKind === 'job' && selectedId === job.id }"
          @click="selectJob(job)"
        >
          <span class="status-dot" :class="{ enabled: job.enabled }" :title="job.enabled ? '已启用' : '未启用'"></span>
          <div class="job-main">
            <strong>{{ job.name }}<span v-if="job.lastStatus === 'failed'" class="name-failed">失败</span></strong>
            <small>{{ job.apiName }} · {{ job.source === "rds" ? "Tushare测试接口" : "Tushare接口" }} · {{ job.cron }}</small>
            <small>上次 {{ job.lastRunAt || "-" }} · 下次 {{ jobNextText(job) }}</small>
          </div>
          <div class="job-ops" @click.stop>
            <input
              type="checkbox"
              :checked="job.enabled"
              :aria-label="`启用 ${job.name}`"
              @change="toggleJob(job, $event)"
            />
            <button type="button" class="text-btn" @click="runJob(job)">运行</button>
          </div>
        </div>
        <p v-if="!standaloneJobs.length && !loadError" class="pane-empty">没有单独调度的任务。</p>
      </aside>

      <div v-if="selectedGroup" class="panel sched-detail">
        <div class="panel-head">
          <h2>{{ selectedGroup.name }}</h2>
          <div class="detail-ops">
            <button type="button" class="ghost-btn" @click="openCreateInGroup">组内新建任务</button>
            <button type="button" class="ghost-btn" @click="runGroup(selectedGroup, false)">运行本组</button>
            <button type="button" class="ghost-btn" @click="runGroup(selectedGroup, true)">按顺序运行</button>
            <button type="button" class="ghost-btn" @click="openEditGroup">编辑</button>
            <button type="button" class="ghost-btn danger" @click="removeGroup(selectedGroup)">删除</button>
          </div>
        </div>
        <dl class="job-meta">
          <div>
            <dt>组间顺序</dt>
            <dd>第 {{ selectedGroupIndex + 1 }} 组</dd>
          </div>
          <div>
            <dt>执行频率</dt>
            <dd>{{ selectedGroup.cron || "不单独定时" }}</dd>
          </div>
          <div>
            <dt>组间接续</dt>
            <dd>{{ selectedGroup.followPrevious ? "上一组成功后自动运行" : "只按本组频率或手动运行" }}</dd>
          </div>
          <div>
            <dt>组内失败</dt>
            <dd>{{ selectedGroup.stopOnFailure ? "停止后续任务" : "继续后续任务" }}</dd>
          </div>
          <div>
            <dt>下次运行</dt>
            <dd>{{ groupNextText(selectedGroup) }}</dd>
          </div>
        </dl>

        <div class="panel-head">
          <h2>组内顺序</h2>
        </div>
        <div class="table-wrap runs-wrap">
          <table v-if="groupMembers.length" class="data runs-table">
            <thead>
              <tr>
                <th>顺序</th>
                <th>任务</th>
                <th>接口</th>
                <th>状态</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(job, index) in groupMembers" :key="job.id" class="member-row" @click="selectJob(job)">
                <td>{{ index + 1 }}</td>
                <td class="left">{{ job.name }}</td>
                <td>{{ job.apiName }}</td>
                <td><span class="run-status" :class="job.lastStatus">{{ statusText(job.lastStatus) }}</span></td>
                <td @click.stop>
                  <button type="button" class="text-btn" :disabled="index === 0" @click="moveSelectedMember(job, -1)">
                    上移
                  </button>
                  <button
                    type="button"
                    class="text-btn"
                    :disabled="index === groupMembers.length - 1"
                    @click="moveSelectedMember(job, 1)"
                  >
                    下移
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="pane-empty">组内还没有任务。可以新建，或编辑已有任务并选择「加入任务组」。</p>
        </div>

        <div class="panel-head">
          <h2>最近运行</h2>
        </div>
        <div class="table-wrap runs-wrap">
          <table v-if="groupRuns.length" class="data runs-table">
            <thead>
              <tr>
                <th>触发</th>
                <th>开始时间</th>
                <th>耗时</th>
                <th>状态</th>
                <th>消息</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="runItem in groupRuns" :key="runItem.id">
                <td>{{ triggerText(runItem.triggerType) }}</td>
                <td>{{ runItem.startedAt }}</td>
                <td>{{ duration(runItem) }}</td>
                <td><span class="run-status" :class="runItem.status">{{ statusText(runItem.status) }}</span></td>
                <td class="left run-msg">{{ runItem.message }}</td>
                <td>
                  <button type="button" class="text-btn" @click="openGroupRunDetail(runItem)">详细信息</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="pane-empty">还没有运行记录。</p>
        </div>
      </div>

      <div v-else-if="selectedJob" class="panel sched-detail">
        <div class="panel-head">
          <h2>{{ selectedJob.name }}</h2>
          <div class="detail-ops">
            <span v-if="selectedJob.groupId" class="detail-pair">
              <button type="button" class="ghost-btn" @click="backToGroup">返回任务组</button>
              <button type="button" class="ghost-btn" :disabled="refreshingRuns" @click="refreshRuns">刷新</button>
              <button type="button" class="ghost-btn" @click="runSelectedJob">运行任务</button>
            </span>
            <button type="button" class="ghost-btn" @click="openEditJob">编辑</button>
            <button type="button" class="ghost-btn danger" @click="removeJob(selectedJob)">删除</button>
          </div>
        </div>
        <dl class="job-meta">
          <div>
            <dt>接口</dt>
            <dd>{{ selectedJob.apiName }}（{{ selectedJob.source === "rds" ? "Tushare测试接口" : "Tushare接口" }}）</dd>
          </div>
          <div>
            <dt>调度</dt>
            <dd v-if="selectedJob.groupId">任务组「{{ groupName(selectedJob.groupId) }}」，按组内顺序</dd>
            <dd v-else>单独调度 · {{ selectedJob.cron }}</dd>
          </div>
          <div>
            <dt>下次运行</dt>
            <dd>{{ jobNextText(selectedJob) }}</dd>
          </div>
          <div>
            <dt>目标表</dt>
            <dd>tusharedata.{{ selectedJob.targetTable }}</dd>
          </div>
          <div>
            <dt>业务主键</dt>
            <dd>{{ selectedJob.primaryKeys.join(", ") || "全量替换" }}</dd>
          </div>
          <div>
            <dt>失败重试</dt>
            <dd>{{ selectedJob.retry }} 次</dd>
          </div>
          <div>
            <dt>水位线</dt>
            <dd>{{ selectedJob.watermark || "-" }}</dd>
          </div>
          <div class="meta-wide">
            <dt>入参</dt>
            <dd>{{ JSON.stringify(selectedJob.params) }}</dd>
          </div>
        </dl>

        <div class="panel-head">
          <h2>最近运行</h2>
        </div>
        <div class="table-wrap runs-wrap">
          <table v-if="runs.length" class="data runs-table">
            <thead>
              <tr>
                <th>触发</th>
                <th>开始时间</th>
                <th>耗时</th>
                <th>状态</th>
                <th>行数</th>
                <th>消息</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="runItem in runs" :key="runItem.id">
                <td>{{ triggerText(runItem.triggerType) }}</td>
                <td>{{ runItem.startedAt }}</td>
                <td>{{ duration(runItem) }}</td>
                <td><span class="run-status" :class="runItem.status">{{ statusText(runItem.status) }}</span></td>
                <td>{{ runItem.rowCount }}</td>
                <td class="left run-msg">{{ runItem.message }}</td>
                <td>
                  <button type="button" class="text-btn" @click="openJobRunDetail(runItem)">详细信息</button>
                  <button v-if="runItem.status === 'failed'" type="button" class="text-btn" @click="retry(runItem)">
                    重跑
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="pane-empty">还没有运行记录。</p>
        </div>
      </div>
      <div v-else class="panel sched-detail">
        <p class="pane-empty">请选择左侧任务组或任务查看详情。</p>
      </div>
    </div>

    <JobDialog
      v-if="dialogOpen"
      :job="editJob"
      :prefill="prefill"
      :groups="groups"
      :initial-group-id="initialGroupId"
      @close="dialogOpen = false"
      @saved="onSaved"
    />
    <GroupDialog v-if="groupDialogOpen" :group="editGroup" @close="groupDialogOpen = false" @saved="onSaved" />
    <RunDetailDialog
      v-if="runDetail"
      :title="runDetail.title"
      :summary="runDetail.summary"
      :calls="runDetail.calls"
      :loading="runDetail.loading"
      :error="runDetail.error"
      @close="closeRunDetail"
    />
  </section>
</template>
