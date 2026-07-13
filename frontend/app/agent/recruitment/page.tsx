"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bot,
  BriefcaseBusiness,
  Check,
  Clipboard,
  Loader2,
  MonitorCheck,
  Plus,
  RefreshCw,
  Save,
  Send,
  Trash2,
  Users,
} from "lucide-react";

import { ResponsiveLayout } from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RegionSelect } from "@/components/recruitment/RegionSelect";
import { toast } from "@/hooks/useToast";
import {
  createRecruitmentCandidate,
  createRecruitmentRequirement,
  createRecruitmentTimelineEvent,
  clickBossMenu,
  deleteAllRecruitmentRequirements,
  deleteRecruitmentRequirement,
  detectBossAssistant,
  fetchBossAssistantStatus,
  fetchRecruitmentCandidates,
  fetchRecruitmentRequirements,
  fetchRecruitmentTimeline,
  generateRecruitmentDraft,
  importBossCandidates,
  runRecruitmentAgent,
  saveBossAssistantConfig,
  searchBossCandidates,
  updateRecruitmentCandidate,
  updateRecruitmentRequirement,
  type BossMenu,
  type BossAssistantStatus,
  type CreateCandidatePayload,
  type CreateRequirementPayload,
  type RecruitmentCandidate,
  type RecruitmentAgentResult,
  type RecruitmentRequirement,
  type RecruitmentTimelineEvent,
  type UpdateCandidatePayload,
} from "@/features/agent/services/recruitmentApi";
import { AIDraftPanel } from "@/components/recruitment/AIDraftPanel";
import type { ChatDraftResult } from "@/features/agent/services/recruitmentApi";

const CONTACT_STATUS_OPTIONS = [
  { value: "new", label: "待筛选" },
  { value: "contacted", label: "已沟通" },
  { value: "replied", label: "已回复" },
  { value: "consented", label: "已同意留资" },
  { value: "group_invited", label: "已邀入群" },
  { value: "rejected", label: "不合适" },
] as const;

const GROUP_STATUS_OPTIONS = [
  { value: "not_invited", label: "未邀请" },
  { value: "invited", label: "已邀请" },
  { value: "joined", label: "已入群" },
  { value: "not_joined", label: "未入群" },
] as const;

const SOURCE_OPTIONS = ["BOSS", "手动导入", "转介绍", "其他"];

const JOB_CATEGORY_OPTIONS = ["不限职位", "服务员", "普工", "普工操作工", "水电工", "化工", "富士康", "铣床工", "手工活", "工厂", "自定义"];
const EDUCATION_OPTIONS = ["不限", "本科及以上", "硕士及以上", "博士", "自定义"];
const EDUCATION_LEVELS = ["初中及以下", "中专/中技", "高中", "大专", "本科", "硕士", "博士"];
const AGE_OPTIONS = ["不限", "20-25", "25-30", "30-35", "35-40", "40-50", "50以上", "自定义"];
const SORT_OPTIONS = ["综合排序", "活跃优先", "匹配度优先"];
const CANDIDATE_BATCH_OPTIONS = [5, 10, 20, 30, 50];
const RECOMMENDED_FILTER_FIELDS = [
  { key: "school", label: "院校要求", options: ["不限", "统招本科", "双一流院校", "211院校", "985院校", "留学生"] },
  { key: "experience", label: "经验要求", options: ["不限", "在校/应届", "25年毕业", "26年毕业", "26年后毕业", "1-3年", "3-5年", "5-10年"] },
  { key: "gender", label: "性别要求", options: ["不限", "男", "女"] },
  { key: "salary", label: "薪资区间", options: ["不限", "1-2K", "2-3K", "3-4K", "4-5K", "5-8K", "8-10K"] },
  { key: "activity", label: "活跃度", options: ["不限", "刚刚活跃", "今日活跃", "3日内活跃", "近一周活跃", "近一个月活跃"] },
  { key: "hopping", label: "跳槽频率", options: ["不限", "5年少于3份", "时间≥1年"] },
  { key: "job_status", label: "求职状态", options: ["不限", "离职-随时到岗", "在职-暂不考虑", "在职-考虑机会", "在职-月内到岗"] },
  { key: "position", label: "职位要求", options: ["不限", "仅从事过此职位", "最近从事此职位", "牛人期望此职位"] },
];
const MAJOR_OPTIONS = [
  {
    category: "工学",
    groups: [
      { name: "仪器类", majors: ["仪器科学与技术", "测控仪器与仪表", "地球物理勘探仪器及方法", "电气测试技术与仪器", "电气检测技术及仪器", "光电信息技术及仪器", "过程检测技术及仪器", "微系统与测控技术", "武器探测与精确制导", "智能监测与控制"] },
      { name: "制药类", majors: ["制药工程", "药物制剂", "生物制药", "化学制药", "药物分析"] },
      { name: "自动化类", majors: ["自动化", "机器人工程", "轨道交通信号与控制", "智能装备与系统", "工业智能"] },
      { name: "安全科学与工程类", majors: ["安全工程", "应急技术与管理"] },
      { name: "兵器类", majors: ["武器系统与工程", "武器发射工程", "探测制导与控制技术", "弹药工程与爆炸技术"] },
      { name: "材料类", majors: ["材料科学与工程", "材料成型及控制工程", "高分子材料与工程", "金属材料工程", "无机非金属材料工程", "复合材料与工程"] },
      { name: "测绘类", majors: ["测绘工程", "遥感科学与技术", "导航工程", "地理空间信息工程"] },
      { name: "船舶与海洋工程类", majors: ["船舶与海洋工程", "海洋工程与技术", "海洋机器人"] },
      { name: "地质类", majors: ["地质工程", "勘查技术与工程", "资源勘查工程", "地下水科学与工程"] },
      { name: "电力电气类", majors: ["电气工程及其自动化", "智能电网信息工程", "电气工程与智能控制", "电机电器智能化"] },
      { name: "机械类", majors: ["机械设计制造及其自动化", "机械电子工程", "工业设计", "过程装备与控制工程", "车辆工程", "智能制造工程"] },
      { name: "计算机类", majors: ["计算机科学与技术", "软件工程", "网络工程", "信息安全", "物联网工程", "数字媒体技术", "数据科学与大数据技术", "人工智能"] },
      { name: "化工与制药类", majors: ["化学工程与工艺", "能源化学工程", "化工安全工程", "涂料工程", "精细化工"] },
      { name: "电子信息类", majors: ["电子信息工程", "电子科学与技术", "通信工程", "微电子科学与工程", "光电信息科学与工程"] },
      { name: "土木类", majors: ["土木工程", "建筑环境与能源应用工程", "给排水科学与工程", "建筑电气与智能化"] },
    ],
  },
  {
    category: "经管类",
    groups: [
      { name: "工商管理类", majors: ["工商管理", "市场营销", "会计学", "财务管理", "人力资源管理", "审计学", "物业管理", "文化产业管理"] },
      { name: "经济学类", majors: ["经济学", "经济统计学", "商务经济学", "国民经济管理"] },
      { name: "金融学类", majors: ["金融学", "金融工程", "保险学", "投资学", "信用管理"] },
      { name: "物流管理类", majors: ["物流管理", "物流工程", "采购管理", "供应链管理"] },
      { name: "电子商务类", majors: ["电子商务", "跨境电子商务"] },
      { name: "旅游管理类", majors: ["旅游管理", "酒店管理", "会展经济与管理"] },
    ],
  },
  {
    category: "教育学",
    groups: [
      { name: "教育类", majors: ["教育学", "教育技术学", "学前教育", "小学教育", "特殊教育", "科学教育", "人文教育"] },
      { name: "体育学类", majors: ["体育教育", "运动训练", "社会体育指导与管理"] },
    ],
  },
  {
    category: "语言类",
    groups: [
      { name: "中国语言文学类", majors: ["汉语言文学", "汉语言", "汉语国际教育", "秘书学"] },
      { name: "外国语言类", majors: ["英语", "商务英语", "日语", "俄语", "德语", "法语", "西班牙语", "阿拉伯语", "朝鲜语"] },
    ],
  },
  {
    category: "医学",
    groups: [
      { name: "临床医学类", majors: ["临床医学", "麻醉学", "医学影像学", "眼视光医学"] },
      { name: "护理药学类", majors: ["护理学", "药学", "临床药学", "康复治疗学", "医学检验技术"] },
      { name: "公共卫生类", majors: ["预防医学", "食品卫生与营养学"] },
    ],
  },
  {
    category: "服务类",
    groups: [
      { name: "餐饮旅游类", majors: ["酒店管理", "旅游管理", "餐饮管理", "烹饪与营养教育"] },
      { name: "公共服务类", majors: ["家政学", "社会工作", "老年服务与管理"] },
    ],
  },
  {
    category: "文史哲类",
    groups: [
      { name: "历史学类", majors: ["历史学", "世界史", "考古学", "文物与博物馆学", "文物保护技术", "外国语言与外国历史", "文化遗产", "古文字学", "科学史"] },
      { name: "哲学类", majors: ["哲学", "逻辑学", "宗教学", "伦理学"] },
      { name: "新闻传播学类", majors: ["新闻学", "广播电视学", "广告学", "传播学", "网络与新媒体"] },
    ],
  },
  {
    category: "理学",
    groups: [
      { name: "数学统计类", majors: ["数学与应用数学", "信息与计算科学", "统计学", "应用统计学"] },
      { name: "物理学类", majors: ["物理学", "应用物理学"] },
      { name: "化学类", majors: ["化学", "应用化学"] },
      { name: "生物科学类", majors: ["生物科学", "生物技术", "生态学"] },
      { name: "心理学类", majors: ["心理学", "应用心理学"] },
    ],
  },
  {
    category: "法学",
    groups: [
      { name: "法学类", majors: ["法学", "知识产权", "监狱学"] },
      { name: "政治学类", majors: ["政治学与行政学", "国际政治", "外交学"] },
      { name: "社会学类", majors: ["社会学", "社会工作", "人类学"] },
    ],
  },
  {
    category: "公安类",
    groups: [
      { name: "公安学类", majors: ["治安学", "侦查学", "边防管理", "禁毒学", "警犬技术"] },
      { name: "公安技术类", majors: ["刑事科学技术", "消防工程", "网络安全与执法"] },
    ],
  },
  {
    category: "艺术学",
    groups: [
      { name: "设计类", majors: ["视觉传达设计", "环境设计", "产品设计", "服装与服饰设计", "数字媒体艺术"] },
      { name: "音乐舞蹈类", majors: ["音乐表演", "音乐学", "舞蹈表演", "舞蹈学"] },
      { name: "戏剧影视类", majors: ["表演", "戏剧影视文学", "广播电视编导", "播音与主持艺术", "动画"] },
      { name: "美术学类", majors: ["美术学", "绘画", "雕塑", "摄影", "书法学"] },
    ],
  },
];

const STAGE_ACTIONS: Array<{ label: string; patch: UpdateCandidatePayload }> = [
  {
    label: "标记已发送",
    patch: {
      contact_status: "contacted",
      next_action: "等待候选人回复；如长时间未回复，由人工判断是否停止跟进。",
    },
  },
  {
    label: "候选人已回复",
    patch: {
      contact_status: "replied",
      next_action: "根据候选人回复继续沟通岗位细节；未明确同意前不记录私人联系方式。",
    },
  },
  {
    label: "同意留资",
    patch: {
      contact_status: "consented",
      consent_to_contact: true,
      next_action: "填写候选人同意提供的联系方式，并确认是否愿意加入微信群或企业微信。",
    },
  },
  {
    label: "已邀入群",
    patch: {
      contact_status: "group_invited",
      group_status: "invited",
      next_action: "等待候选人入群，入群后交给私域承接。",
    },
  },
  {
    label: "已入群",
    patch: {
      group_status: "joined",
      next_action: "已进入私域，后续由群内业务介绍 Agent 承接。",
    },
  },
  {
    label: "停止跟进",
    patch: {
      contact_status: "rejected",
      next_action: "停止跟进，保留沟通记录。",
    },
  },
];

const emptyRequirement: CreateRequirementPayload = {
  title: "",
  role: "",
  job_category: "不限职位",
  location: "",
  search_keyword: "",
  education_requirement: "不限",
  age_requirement: "不限",
  recommended_filters: "",
  sort_preference: "综合排序",
  filter_viewed_14_days: false,
  filter_exchanged_30_days: false,
  batch_size: 10,
  tags: "",
  must_have: "",
  nice_have: "",
  description: "",
  status: "active",
};

const emptyCandidate: Omit<CreateCandidatePayload, "requirement_id"> = {
  name: "",
  source: "BOSS",
  current_role: "",
  location: "",
  tags: "",
  profile: "",
};

function scoreBadgeClass(score: number): string {
  if (score >= 75) return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (score >= 45) return "bg-amber-100 text-amber-700 border-amber-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
}

function statusLabel(value: string): string {
  return CONTACT_STATUS_OPTIONS.find((item) => item.value === value)?.label ?? value;
}

function eventTypeLabel(value: string): string {
  switch (value) {
    case "candidate_created":
      return "加入";
    case "agent_run":
      return "Agent";
    case "draft_generated":
      return "话术";
    case "status_changed":
      return "状态";
    case "group_changed":
      return "私域";
    case "message_recorded":
      return "回复";
    case "consent_changed":
      return "同意";
    case "contact_recorded":
      return "留资";
    default:
      return "记录";
  }
}

function formatTimelineTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isCustomEducationRange(value: string): boolean {
  return value.includes("-");
}

function isBlankJobCategory(value: string): boolean {
  return !value.trim() || value.includes("不限") || value === "自定义";
}

function buildRequirementRole(form: CreateRequirementPayload): string {
  const category = isBlankJobCategory(form.job_category) ? "" : form.job_category.trim();
  return form.search_keyword.trim() || category || form.role.trim();
}

function buildBossSearchKeyword(form: CreateRequirementPayload): string {
  const category = isBlankJobCategory(form.job_category) ? "" : form.job_category.trim();
  return form.search_keyword.trim() || category;
}

function buildRequirementPayload(form: CreateRequirementPayload): CreateRequirementPayload {
  const role = buildRequirementRole(form);
  const location = form.location.trim();
  const searchKeyword = buildBossSearchKeyword(form);
  return {
    ...form,
    title: form.title.trim() || [location, role].filter(Boolean).join(" ") || role,
    role,
    search_keyword: searchKeyword,
    tags: "",
    must_have: "",
    nice_have: "",
    description: "",
  };
}

function educationRangeParts(value: string): { min: string; max: string } {
  const [min, max] = value.split("-");
  if (EDUCATION_LEVELS.includes(min) && EDUCATION_LEVELS.includes(max)) {
    return { min, max };
  }
  return { min: "大专", max: "博士" };
}

function buildEducationRange(min: string, max: string): string {
  const minIndex = EDUCATION_LEVELS.indexOf(min);
  const maxIndex = EDUCATION_LEVELS.indexOf(max);
  if (minIndex < 0 || maxIndex < 0) return "大专-博士";
  return minIndex <= maxIndex ? `${min}-${max}` : `${max}-${min}`;
}

function defaultRecommendedFilters(): Record<string, string> {
  return Object.fromEntries([
    ...RECOMMENDED_FILTER_FIELDS.map((field) => [field.key, "不限"]),
    ["major", ""],
  ]);
}

function parseRecommendedFilters(raw: string): Record<string, string> {
  const values = defaultRecommendedFilters();
  raw
    .split(/[;；]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((item) => {
      const [label, ...rest] = item.split(/[:：=]/);
      const value = rest.join(":").trim();
      const field = RECOMMENDED_FILTER_FIELDS.find((candidate) => candidate.label === label.trim());
      if (field && value) values[field.key] = value;
      if (label.trim() === "专业要求" && value) values.major = value;
    });
  return values;
}

function serializeRecommendedFilters(values: Record<string, string>): string {
  return [
    ...RECOMMENDED_FILTER_FIELDS.map((field) => {
      const value = values[field.key]?.trim();
      return value && value !== "不限" ? `${field.label}:${value}` : "";
    }),
    values.major?.trim() ? `专业要求:${values.major.trim()}` : "",
  ]
    .filter(Boolean)
    .join("; ");
}

function majorOptionLabel(value: string): string {
  const parts = value.split("/").filter(Boolean);
  if (parts.length === 1) return parts[0];
  if (parts[parts.length - 1] === "全部") return parts.slice(0, -1).join(" / ");
  return parts.join(" / ");
}

function isStageActionApplied(candidate: RecruitmentCandidate, patch: UpdateCandidatePayload): boolean {
  if (patch.contact_status && candidate.contact_status !== patch.contact_status) return false;
  if (patch.group_status && candidate.group_status !== patch.group_status) return false;
  if (patch.consent_to_contact !== undefined && candidate.consent_to_contact !== patch.consent_to_contact) return false;
  return Boolean(patch.contact_status || patch.group_status || patch.consent_to_contact !== undefined);
}

export default function RecruitmentPage({ embedded = false }: { embedded?: boolean }) {
  const router = useRouter();
  const [requirements, setRequirements] = useState<RecruitmentRequirement[]>([]);
  const [candidates, setCandidates] = useState<RecruitmentCandidate[]>([]);
  const [selectedRequirementId, setSelectedRequirementId] = useState<number | null>(null);
  const [requirementForm, setRequirementForm] = useState<CreateRequirementPayload>(emptyRequirement);
  const [candidateForm, setCandidateForm] = useState<Omit<CreateCandidatePayload, "requirement_id">>(emptyCandidate);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [chatDrafts, setChatDrafts] = useState<Record<number, ChatDraftResult>>({});
  const [generatingChatDraftId, setGeneratingChatDraftId] = useState<number | null>(null);
  const [agentResults, setAgentResults] = useState<Record<number, RecruitmentAgentResult>>({});
  const [timelines, setTimelines] = useState<Record<number, RecruitmentTimelineEvent[]>>({});
  const [timelineDrafts, setTimelineDrafts] = useState<Record<number, string>>({});
  const [loadingRequirements, setLoadingRequirements] = useState(false);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [savingRequirement, setSavingRequirement] = useState(false);
  const [deletingRequirementId, setDeletingRequirementId] = useState<number | null>(null);
  const [requirementQuery, setRequirementQuery] = useState("");
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [deleteAllPassword, setDeleteAllPassword] = useState("");
  const [deletingAllRequirements, setDeletingAllRequirements] = useState(false);
  const [savingCandidate, setSavingCandidate] = useState(false);
  const [savingCandidateId, setSavingCandidateId] = useState<number | null>(null);
  const [draftingCandidateId, setDraftingCandidateId] = useState<number | null>(null);
  const [runningAgentCandidateId, setRunningAgentCandidateId] = useState<number | null>(null);
  const [addingTimelineCandidateId, setAddingTimelineCandidateId] = useState<number | null>(null);
  const [advancingCandidateId, setAdvancingCandidateId] = useState<number | null>(null);
  const [bossStatus, setBossStatus] = useState<BossAssistantStatus | null>(null);
  const [bossPath, setBossPath] = useState("");
  const [checkingBoss, setCheckingBoss] = useState(false);
  const [savingBossPath, setSavingBossPath] = useState(false);
  const [clickingBossMenu, setClickingBossMenu] = useState<BossMenu | null>(null);
  const [syncingBossCandidates, setSyncingBossCandidates] = useState(false);
  const [majorDialogOpen, setMajorDialogOpen] = useState(false);
  const [majorCategory, setMajorCategory] = useState(MAJOR_OPTIONS[0].category);
  const [majorGroup, setMajorGroup] = useState(MAJOR_OPTIONS[0].groups[0].name);
  const [majorDraft, setMajorDraft] = useState("");
  const [majorSearch, setMajorSearch] = useState("");

  const selectedRequirement = useMemo(
    () => requirements.find((item) => item.id === selectedRequirementId) ?? null,
    [requirements, selectedRequirementId]
  );

  const filteredRequirements = useMemo(() => {
    const keyword = requirementQuery.trim().toLowerCase();
    if (!keyword) return requirements;
    return requirements.filter((item) =>
      [
        item.title,
        item.role,
        item.job_category,
        item.location,
        item.search_keyword,
        item.education_requirement,
        item.age_requirement,
        item.recommended_filters,
        item.sort_preference,
        item.status,
      ]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(keyword))
    );
  }, [requirements, requirementQuery]);

  const activeCandidates = useMemo(
    () => candidates.filter((item) => item.contact_status !== "rejected"),
    [candidates]
  );

  const consentedCount = useMemo(
    () => candidates.filter((item) => item.consent_to_contact).length,
    [candidates]
  );

  const recommendedFilterValues = useMemo(
    () => parseRecommendedFilters(requirementForm.recommended_filters),
    [requirementForm.recommended_filters]
  );
  const activeMajorCategory = MAJOR_OPTIONS.find((item) => item.category === majorCategory) ?? MAJOR_OPTIONS[0];
  const activeMajorGroup = activeMajorCategory.groups.find((item) => item.name === majorGroup) ?? activeMajorCategory.groups[0];
  const majorSearchResults = useMemo(() => {
    const keyword = majorSearch.trim().toLowerCase();
    if (!keyword) return [];
    return MAJOR_OPTIONS.flatMap((category) =>
      category.groups.flatMap((group) =>
        ["全部", ...group.majors].map((major) => {
          const value = `${category.category}/${group.name}/${major}`;
          return { label: major === "全部" ? `${category.category} / ${group.name}` : value, value };
        })
      )
    )
      .filter((item) => item.label.toLowerCase().includes(keyword))
      .slice(0, 30);
  }, [majorSearch]);

  function patchRecommendedFilter(key: string, value: string) {
    setRequirementForm((prev) => {
      const values = parseRecommendedFilters(prev.recommended_filters);
      values[key] = value;
      return { ...prev, recommended_filters: serializeRecommendedFilters(values) };
    });
  }

  function openMajorDialog() {
    const parts = (recommendedFilterValues.major ?? "").split("/").filter(Boolean);
    const category = MAJOR_OPTIONS.find((item) => item.category === parts[0]) ?? MAJOR_OPTIONS[0];
    const group = category.groups.find((item) => item.name === parts[1]) ?? category.groups[0];
    setMajorCategory(category.category);
    setMajorGroup(group.name);
    setMajorDraft(recommendedFilterValues.major ?? "");
    setMajorSearch("");
    setMajorDialogOpen(true);
  }

  function confirmMajorDialog() {
    patchRecommendedFilter("major", majorDraft.trim() || majorSearch.trim());
    setMajorSearch("");
    setMajorDialogOpen(false);
  }

  async function loadRequirements() {
    try {
      setLoadingRequirements(true);
      const data = await fetchRecruitmentRequirements();
      setRequirements(data);
      setSelectedRequirementId((current) => {
        if (current && data.some((item) => item.id === current)) return current;
        return data[0]?.id ?? null;
      });
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setLoadingRequirements(false);
    }
  }

  async function loadCandidates(requirementId: number | null) {
    try {
      setLoadingCandidates(true);
      const data = await fetchRecruitmentCandidates(requirementId);
      setCandidates(data);
      void loadCandidateTimelines(data);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setLoadingCandidates(false);
    }
  }

  async function loadCandidateTimeline(candidateId: number) {
    const events = await fetchRecruitmentTimeline(candidateId);
    setTimelines((prev) => ({ ...prev, [candidateId]: events }));
  }

  async function loadCandidateTimelines(items: RecruitmentCandidate[]) {
    await Promise.all(items.map((item) => loadCandidateTimeline(item.id).catch(() => undefined)));
  }

  function applyBossStatus(data: BossAssistantStatus) {
    setBossStatus(data);
    setBossPath(data.saved_exe_path || data.exe_path || "");
  }

  async function loadBossStatus() {
    try {
      setCheckingBoss(true);
      const data = await fetchBossAssistantStatus();
      applyBossStatus(data);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setCheckingBoss(false);
    }
  }

  async function handleDetectBoss() {
    try {
      setCheckingBoss(true);
      const data = await detectBossAssistant();
      applyBossStatus(data);
      toast.success(data.detected ? "已检测到 BOSS 网页/客户端" : "未检测到 BOSS 网页/客户端");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setCheckingBoss(false);
    }
  }

  async function handleSaveBossPath() {
    if (!bossPath.trim()) {
      toast.error("请先填写 BOSS 客户端路径");
      return;
    }
    try {
      setSavingBossPath(true);
      const data = await saveBossAssistantConfig(bossPath.trim());
      applyBossStatus(data);
      toast.success("BOSS 客户端路径已保存");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setSavingBossPath(false);
    }
  }

  async function handleClickBossMenu(menu: BossMenu) {
    try {
      setClickingBossMenu(menu);
      await clickBossMenu(menu);
      toast.success("已点击 BOSS 菜单，请在 BOSS 页面确认");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setClickingBossMenu(null);
    }
  }

  useEffect(() => {
    const userId = localStorage.getItem("agent_user_id");
    if (!userId) {
      router.push("/agent/login");
      return;
    }
    void loadRequirements();
    void loadBossStatus();
  }, [router]);

  useEffect(() => {
    void loadCandidates(selectedRequirementId);
  }, [selectedRequirementId]);

  async function handleCreateRequirement() {
    try {
      setSavingRequirement(true);
      const payload = buildRequirementPayload(requirementForm);
      const created = await createRecruitmentRequirement(payload);
      setRequirements((prev) => [created, ...prev]);
      setSelectedRequirementId(created.id);
      try {
        await searchBossCandidates(payload);
        await syncBossCandidates(created.id, payload.batch_size);
        void loadBossStatus();
        toast.success("BOSS search synced");
      } catch (bossError) {
        toast.error(`BOSS同步失败: ${(bossError as Error).message}`);
      }
      toast.success("招聘需求已创建");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setSavingRequirement(false);
    }
  }

  async function syncBossCandidates(requirementId: number, limit: number) {
    try {
      setSyncingBossCandidates(true);
      const result = await importBossCandidates(requirementId, limit);
      await loadCandidates(requirementId);
      toast.success(`BOSS候选人已同步：新增 ${result.imported}，跳过 ${result.skipped}`);
    } finally {
      setSyncingBossCandidates(false);
    }
  }

  async function handleSyncBossCandidates() {
    if (!selectedRequirement) {
      toast.error("请先选择招聘需求");
      return;
    }
    try {
      await syncBossCandidates(selectedRequirement.id, selectedRequirement.batch_size);
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  async function handlePauseRequirement(requirement: RecruitmentRequirement) {
    try {
      const nextStatus = requirement.status === "active" ? "paused" : "active";
      const updated = await updateRecruitmentRequirement(requirement.id, {
        title: requirement.title,
        role: requirement.role,
        job_category: requirement.job_category,
        location: requirement.location,
        search_keyword: requirement.search_keyword,
        education_requirement: requirement.education_requirement,
        age_requirement: requirement.age_requirement,
        recommended_filters: requirement.recommended_filters,
        sort_preference: requirement.sort_preference,
        filter_viewed_14_days: requirement.filter_viewed_14_days,
        filter_exchanged_30_days: requirement.filter_exchanged_30_days,
        batch_size: requirement.batch_size,
        tags: requirement.tags,
        must_have: requirement.must_have,
        nice_have: requirement.nice_have,
        description: requirement.description,
        status: nextStatus,
      });
      setRequirements((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      toast.error((error as Error).message);
    }
  }

  async function handleDeleteRequirement(requirement: RecruitmentRequirement) {
    if (!window.confirm(`确定删除需求“${requirement.title}”？关联候选人和沟通记录也会一起删除。`)) return;
    try {
      setDeletingRequirementId(requirement.id);
      await deleteRecruitmentRequirement(requirement.id);
      const nextRequirements = requirements.filter((item) => item.id !== requirement.id);
      setRequirements(nextRequirements);
      if (selectedRequirementId === requirement.id) {
        setSelectedRequirementId(nextRequirements[0]?.id ?? null);
        setCandidates([]);
      }
      toast.success("需求已删除");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setDeletingRequirementId(null);
    }
  }

  async function handleDeleteAllRequirements() {
    if (!deleteAllPassword.trim()) {
      toast.error("请输入当前账号密码");
      return;
    }
    try {
      setDeletingAllRequirements(true);
      await deleteAllRecruitmentRequirements(deleteAllPassword);
      setRequirements([]);
      setSelectedRequirementId(null);
      setCandidates([]);
      setTimelines({});
      setDeleteAllPassword("");
      setDeleteAllDialogOpen(false);
      toast.success("全部需求已删除");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setDeletingAllRequirements(false);
    }
  }

  async function handleCreateCandidate() {
    if (!selectedRequirementId) {
      toast.error("请先选择招聘需求");
      return;
    }
    try {
      setSavingCandidate(true);
      const created = await createRecruitmentCandidate({
        ...candidateForm,
        requirement_id: selectedRequirementId,
      });
      setCandidates((prev) => [created, ...prev]);
      setCandidateForm(emptyCandidate);
      void loadCandidateTimeline(created.id);
      toast.success("候选人已加入线索池");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setSavingCandidate(false);
    }
  }

  function patchCandidate(id: number, patch: Partial<RecruitmentCandidate>) {
    setCandidates((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  async function handleSaveCandidate(candidate: RecruitmentCandidate) {
    try {
      setSavingCandidateId(candidate.id);
      const updated = await updateRecruitmentCandidate(candidate.id, {
        name: candidate.name,
        source: candidate.source,
        current_role: candidate.current_role,
        location: candidate.location,
        tags: candidate.tags,
        profile: candidate.profile,
        contact_status: candidate.contact_status,
        consent_to_contact: candidate.consent_to_contact,
        private_contact: candidate.private_contact,
        group_status: candidate.group_status,
        last_message: candidate.last_message,
        next_action: candidate.next_action,
      });
      patchCandidate(candidate.id, updated);
      void loadCandidateTimeline(candidate.id);
      toast.success("候选人已更新");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setSavingCandidateId(null);
    }
  }

  async function handleAdvanceCandidate(candidate: RecruitmentCandidate, patch: UpdateCandidatePayload) {
    try {
      setAdvancingCandidateId(candidate.id);
      const updated = await updateRecruitmentCandidate(candidate.id, patch);
      patchCandidate(candidate.id, updated);
      void loadCandidateTimeline(candidate.id);
      toast.success("候选人状态已推进");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setAdvancingCandidateId(null);
    }
  }

  async function handleGenerateDraft(candidateId: number) {
    try {
      setDraftingCandidateId(candidateId);
      const draft = await generateRecruitmentDraft(candidateId);
      setDrafts((prev) => ({ ...prev, [candidateId]: draft }));
      void loadCandidateTimeline(candidateId);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setDraftingCandidateId(null);
    }
  }

  async function handleRunAgent(candidateId: number) {
    try {
      setRunningAgentCandidateId(candidateId);
      const { result, candidate } = await runRecruitmentAgent(candidateId);
      patchCandidate(candidate.id, candidate);
      if (result.draft) {
        setDrafts((prev) => ({ ...prev, [candidateId]: result.draft }));
      }
      setAgentResults((prev) => ({ ...prev, [candidateId]: result }));
      void loadCandidateTimeline(candidateId);
      toast.success(result.mode === "local" ? "已用本地规则运行 Agent" : "招聘 Agent 已运行");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setRunningAgentCandidateId(null);
    }
  }

  async function handleCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("已复制");
    } catch {
      toast.error("复制失败");
    }
  }

  function handleChatDraftGenerated(candidateId: number, result: ChatDraftResult) {
    setChatDrafts((prev) => ({ ...prev, [candidateId]: result }));
    setGeneratingChatDraftId(null);
  }

  async function handleAddTimelineEvent(candidateId: number) {
    const content = (timelineDrafts[candidateId] ?? "").trim();
    if (!content) {
      toast.error("请先填写沟通记录");
      return;
    }
    try {
      setAddingTimelineCandidateId(candidateId);
      const event = await createRecruitmentTimelineEvent(candidateId, {
        event_type: "manual_note",
        title: "人工记录",
        content,
      });
      setTimelines((prev) => ({ ...prev, [candidateId]: [event, ...(prev[candidateId] ?? [])] }));
      setTimelineDrafts((prev) => ({ ...prev, [candidateId]: "" }));
      toast.success("沟通进展已记录");
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setAddingTimelineCandidateId(null);
    }
  }

  const headerContent = (
    <div className="border-b bg-card p-3 shadow-sm sm:p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">招聘 Agent</h1>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span>需求 {requirements.length}</span>
            <span>候选人 {candidates.length}</span>
            <span>可跟进 {activeCandidates.length}</span>
            <span>已同意留资 {consentedCount}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void loadRequirements()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
          {!embedded && (
            <Button variant="outline" size="sm" onClick={() => router.push("/agent/dashboard")}>
              返回
            </Button>
          )}
        </div>
      </div>
    </div>
  );

  const mainContent = (
    <div className="flex-1 overflow-auto p-3 sm:p-4 md:p-6">
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex flex-col gap-2 text-base sm:flex-row sm:items-center sm:justify-between">
              <span className="flex items-center gap-2">
                <MonitorCheck className="h-4 w-4" />
                BOSS 本地助手
              </span>
              <Badge
                variant="outline"
                className={
                  bossStatus?.detected
                    ? "w-fit border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "w-fit border-slate-200 bg-slate-50 text-slate-600"
                }
              >
                {bossStatus?.detected ? "已检测到网页/客户端" : "未检测到网页/客户端"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-1 text-sm">
                <div className="font-medium text-foreground">
                  {bossStatus?.detected
                    ? `${bossStatus.window_title || "BOSS直聘"} 正在运行`
                    : "请先手动打开并登录 BOSS 直聘网页或客户端"}
                </div>
                <div className="text-xs text-muted-foreground">
                  网页检测需要 Chrome 当前标签停在 BOSS；项目不保存 BOSS 账号、密码、cookie 或登录态。
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => void handleDetectBoss()} disabled={checkingBoss}>
                {checkingBoss ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                检测网页/客户端
              </Button>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleClickBossMenu("search")}
                disabled={clickingBossMenu !== null}
              >
                {clickingBossMenu === "search" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                打开BOSS搜索
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleClickBossMenu("chat")}
                disabled={clickingBossMenu !== null}
              >
                {clickingBossMenu === "chat" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                打开BOSS沟通
              </Button>
            </div>

            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
              <div>
                <Label className="mb-1 block text-sm font-medium">客户端路径（可选）</Label>
                <Input
                  value={bossPath}
                  onChange={(event) => setBossPath(event.target.value)}
                  placeholder="例如：D:\\bosszhipin\\boss-zhipin\\boss-zhipin.exe"
                />
              </div>
              <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                <div>窗口：{bossStatus?.visible ? "可见" : "未确认"}</div>
                <div>最小化：{bossStatus?.minimized ? "是" : "否"}</div>
                <div>
                  尺寸：
                  {bossStatus?.window_width && bossStatus?.window_height
                    ? `${bossStatus.window_width} x ${bossStatus.window_height}`
                    : "-"}
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <div>
                {bossStatus?.process_name
                  ? `进程：${bossStatus.process_name} #${bossStatus.process_id}`
                  : "当前可检测 Chrome 网页或桌面客户端；候选人资料仍由人工复制/粘贴。"}
                {bossStatus?.last_checked_at ? ` · ${bossStatus.last_checked_at}` : ""}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleSaveBossPath()}
                disabled={savingBossPath || !bossPath.trim()}
              >
                {savingBossPath ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                保存路径
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <BriefcaseBusiness className="h-4 w-4" />
                新建需求
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                type="hidden"
                value={requirementForm.title}
                onChange={(event) => setRequirementForm((prev) => ({ ...prev, title: event.target.value }))}
                placeholder="如：本周水电工补员"
              />
              <div className="hidden">
                <Input
                  value={requirementForm.role}
                  onChange={(event) => setRequirementForm((prev) => ({ ...prev, role: event.target.value }))}
                  placeholder="岗位"
                />
                <RegionSelect
                  value={requirementForm.location}
                  onChange={(location) => setRequirementForm((prev) => ({ ...prev, location }))}
                />
              </div>
              <div className="space-y-3 rounded-md border bg-muted/20 p-3">
                <div className="text-sm font-medium">BOSS搜索条件</div>
                <RegionSelect
                  value={requirementForm.location}
                  onChange={(location) => setRequirementForm((prev) => ({ ...prev, location }))}
                  bossMode
                />
                <div className="grid gap-2 sm:grid-cols-2">
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={requirementForm.job_category}
                    onChange={(event) => setRequirementForm((prev) => ({ ...prev, job_category: event.target.value }))}
                  >
                    {JOB_CATEGORY_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <Input
                    value={requirementForm.search_keyword}
                    onChange={(event) => setRequirementForm((prev) => ({ ...prev, search_keyword: event.target.value }))}
                    placeholder="搜索职位关键词，如：服务员"
                  />
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={
                      isCustomEducationRange(requirementForm.education_requirement)
                        ? "自定义"
                        : requirementForm.education_requirement
                    }
                    onChange={(event) => {
                      const value = event.target.value;
                      setRequirementForm((prev) => ({
                        ...prev,
                        education_requirement: value === "自定义" ? buildEducationRange("大专", "博士") : value,
                      }));
                    }}
                  >
                    {EDUCATION_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        学历：{item}
                      </option>
                    ))}
                  </select>
                  {isCustomEducationRange(requirementForm.education_requirement) && (
                    <div className="grid gap-2 rounded-md border bg-background p-2 sm:col-span-2 sm:grid-cols-2">
                      <select
                        className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                        value={educationRangeParts(requirementForm.education_requirement).min}
                        onChange={(event) => {
                          const range = educationRangeParts(requirementForm.education_requirement);
                          setRequirementForm((prev) => ({
                            ...prev,
                            education_requirement: buildEducationRange(event.target.value, range.max),
                          }));
                        }}
                      >
                        {EDUCATION_LEVELS.map((item) => (
                          <option key={item} value={item}>
                            最低：{item}
                          </option>
                        ))}
                      </select>
                      <select
                        className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                        value={educationRangeParts(requirementForm.education_requirement).max}
                        onChange={(event) => {
                          const range = educationRangeParts(requirementForm.education_requirement);
                          setRequirementForm((prev) => ({
                            ...prev,
                            education_requirement: buildEducationRange(range.min, event.target.value),
                          }));
                        }}
                      >
                        {EDUCATION_LEVELS.map((item) => (
                          <option key={item} value={item}>
                            最高：{item}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={requirementForm.age_requirement}
                    onChange={(event) => setRequirementForm((prev) => ({ ...prev, age_requirement: event.target.value }))}
                  >
                    {AGE_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        年龄：{item}
                      </option>
                    ))}
                  </select>
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={requirementForm.sort_preference}
                    onChange={(event) => setRequirementForm((prev) => ({ ...prev, sort_preference: event.target.value }))}
                  >
                    {SORT_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <select
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                    value={requirementForm.batch_size}
                    onChange={(event) =>
                      setRequirementForm((prev) => ({ ...prev, batch_size: Number(event.target.value) || 10 }))
                    }
                  >
                    {CANDIDATE_BATCH_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        同步候选人：{item}个
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-2 rounded-md border bg-background p-2 sm:grid-cols-2">
                  <div className="text-xs font-medium text-muted-foreground sm:col-span-2">推荐筛选 / 更多筛选</div>
                  {RECOMMENDED_FILTER_FIELDS.map((field) => (
                    <select
                      key={field.key}
                      className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                      value={recommendedFilterValues[field.key] ?? "不限"}
                      onChange={(event) => patchRecommendedFilter(field.key, event.target.value)}
                    >
                      {field.options.map((item) => (
                        <option key={item} value={item}>
                          {field.label}：{item}
                        </option>
                      ))}
                    </select>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10 justify-start px-3 text-left font-normal sm:col-span-2"
                    onClick={openMajorDialog}
                  >
                    专业要求：{recommendedFilterValues.major ? majorOptionLabel(recommendedFilterValues.major) : "不限"}
                  </Button>
                </div>
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2">
                    <Checkbox
                      checked={requirementForm.filter_viewed_14_days}
                      onCheckedChange={(value) =>
                        setRequirementForm((prev) => ({ ...prev, filter_viewed_14_days: Boolean(value) }))
                      }
                    />
                    过滤近14天查看
                  </label>
                  <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2">
                    <Checkbox
                      checked={requirementForm.filter_exchanged_30_days}
                      onCheckedChange={(value) =>
                        setRequirementForm((prev) => ({ ...prev, filter_exchanged_30_days: Boolean(value) }))
                      }
                    />
                    近30天未和同事交换简历
                  </label>
                </div>
              </div>
              <Button
                className="w-full"
                onClick={() => void handleCreateRequirement()}
                disabled={savingRequirement || !buildRequirementRole(requirementForm)}
              >
                {savingRequirement ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                创建需求
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center justify-between gap-2 text-base">
                <span>需求列表</span>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteAllDialogOpen(true)}
                  disabled={requirements.length === 0 || deletingAllRequirements}
                >
                  一键删除全部
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Input
                value={requirementQuery}
                onChange={(event) => setRequirementQuery(event.target.value)}
                placeholder="搜索需求、位置、岗位、关键词"
              />
              {loadingRequirements ? (
                <div className="py-8 text-center text-sm text-muted-foreground">加载中...</div>
              ) : requirements.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">暂无需求</div>
              ) : filteredRequirements.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">未找到匹配需求</div>
              ) : (
                filteredRequirements.map((item) => (
                  <div
                    key={item.id}
                    className={`w-full rounded-md border p-3 text-left transition-colors ${
                      selectedRequirementId === item.id
                        ? "border-green-500 bg-green-50"
                        : "border-border bg-background hover:bg-muted/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <button className="min-w-0 flex-1 text-left" type="button" onClick={() => setSelectedRequirementId(item.id)}>
                        <div className="truncate text-sm font-medium text-foreground">{item.title}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {item.role || "-"} · {item.location || "不限地点"}
                        </div>
                      </button>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge variant="outline">
                          {item.status === "active" ? "进行中" : item.status === "paused" ? "暂停" : "关闭"}
                        </Badge>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          onClick={() => void handleDeleteRequirement(item)}
                          disabled={deletingRequirementId === item.id}
                          title="删除需求"
                        >
                          {deletingRequirementId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center justify-between gap-3 text-base">
                <span className="flex min-w-0 items-center gap-2">
                  <Users className="h-4 w-4 shrink-0" />
                  <span className="truncate">{selectedRequirement?.title ?? "候选人池"}</span>
                </span>
                {selectedRequirement && (
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleSyncBossCandidates()}
                      disabled={syncingBossCandidates}
                    >
                      {syncingBossCandidates ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                      同步BOSS候选人
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void handlePauseRequirement(selectedRequirement)}>
                      {selectedRequirement.status === "active" ? "暂停" : "恢复"}
                    </Button>
                  </div>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
              <div className="grid gap-2 sm:grid-cols-2">
                <Input
                  value={candidateForm.name}
                  onChange={(event) => setCandidateForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="候选人"
                />
                <select
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                  value={candidateForm.source}
                  onChange={(event) => setCandidateForm((prev) => ({ ...prev, source: event.target.value }))}
                >
                  {SOURCE_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
                <Input
                  value={candidateForm.current_role}
                  onChange={(event) => setCandidateForm((prev) => ({ ...prev, current_role: event.target.value }))}
                  placeholder="当前岗位/标题"
                />
                <RegionSelect
                  value={candidateForm.location}
                  onChange={(location) => setCandidateForm((prev) => ({ ...prev, location }))}
                />
                <Input
                  className="sm:col-span-2"
                  value={candidateForm.tags}
                  onChange={(event) => setCandidateForm((prev) => ({ ...prev, tags: event.target.value }))}
                  placeholder="候选人标签"
                />
                <Textarea
                  className="min-h-24 sm:col-span-2"
                  value={candidateForm.profile}
                  onChange={(event) => setCandidateForm((prev) => ({ ...prev, profile: event.target.value }))}
                  placeholder="资料摘要、经历、沟通记录"
                />
              </div>
              <div className="flex flex-col justify-between rounded-md border bg-muted/30 p-3">
                <div className="space-y-2 text-sm">
                  <div className="font-medium text-foreground">匹配基准</div>
                  <div className="text-muted-foreground">{selectedRequirement?.role || "未选择岗位"}</div>
                  <div className="text-muted-foreground">{selectedRequirement?.recommended_filters || "未设置推荐筛选"}</div>
                </div>
                <Button
                  className="mt-4"
                  onClick={() => void handleCreateCandidate()}
                  disabled={savingCandidate || !selectedRequirementId || !candidateForm.name.trim()}
                >
                  {savingCandidate ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                  加入候选人池
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-3">
            {loadingCandidates ? (
              <Card>
                <CardContent className="py-12 text-center text-sm text-muted-foreground">加载中...</CardContent>
              </Card>
            ) : candidates.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-sm text-muted-foreground">暂无候选人</CardContent>
              </Card>
            ) : (
              candidates.map((candidate) => {
                const draft = drafts[candidate.id] ?? "";
                const agentResult = agentResults[candidate.id];
                const timeline = timelines[candidate.id] ?? [];
                const timelineDraft = timelineDrafts[candidate.id] ?? "";
                return (
                  <Card key={candidate.id}>
                    <CardContent className="space-y-4 p-4">
                      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Input
                              className="h-9 w-44 font-medium"
                              value={candidate.name}
                              onChange={(event) => patchCandidate(candidate.id, { name: event.target.value })}
                            />
                            <Badge variant="outline" className={scoreBadgeClass(candidate.match_score)}>
                              {candidate.match_score}
                            </Badge>
                            <Badge variant="outline">{statusLabel(candidate.contact_status)}</Badge>
                          </div>
                          <div className="mt-2 text-xs text-muted-foreground">{candidate.match_reason}</div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void handleRunAgent(candidate.id)}
                            disabled={runningAgentCandidateId === candidate.id}
                          >
                            {runningAgentCandidateId === candidate.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Bot className="mr-2 h-4 w-4" />
                            )}
                            运行 Agent
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void handleGenerateDraft(candidate.id)}
                            disabled={draftingCandidateId === candidate.id}
                          >
                            {draftingCandidateId === candidate.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Send className="mr-2 h-4 w-4" />
                            )}
                            生成话术
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => void handleSaveCandidate(candidate)}
                            disabled={savingCandidateId === candidate.id}
                          >
                            {savingCandidateId === candidate.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Check className="mr-2 h-4 w-4" />
                            )}
                            保存
                          </Button>
                        </div>
                      </div>

                      <div className="rounded-md border bg-muted/20 p-3">
                        <div className="mb-2 text-sm font-medium">状态推进</div>
                        <div className="flex flex-wrap gap-2">
                          {STAGE_ACTIONS.map((action) => {
                            const applied = isStageActionApplied(candidate, action.patch);
                            return (
                              <Button
                                key={action.label}
                                variant={applied ? "default" : "outline"}
                                size="sm"
                                onClick={() => void handleAdvanceCandidate(candidate, action.patch)}
                                disabled={advancingCandidateId === candidate.id || applied}
                              >
                                {advancingCandidateId === candidate.id && !applied ? (
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : null}
                                {action.label}
                              </Button>
                            );
                          })}
                        </div>
                      </div>

                      {agentResult && (
                        <div className="rounded-md border border-blue-100 bg-blue-50/60 p-3">
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <div className="text-sm font-medium text-blue-950">Agent 状态流</div>
                            <Badge variant="outline" className="border-blue-200 bg-white text-blue-700">
                              {agentResult.mode || "langgraph"}
                            </Badge>
                            <Badge variant="outline" className="border-blue-200 bg-white text-blue-700">
                              {agentResult.stage}
                            </Badge>
                            {agentResult.requires_human_approval && (
                              <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">
                                需人工确认
                              </Badge>
                            )}
                          </div>
                          <div className="grid gap-2 text-xs text-blue-900 md:grid-cols-3">
                            {agentResult.events.map((event, index) => (
                              <div key={`${event.step}-${index}`} className="rounded border border-blue-100 bg-white/80 p-2">
                                <div className="font-medium">{event.step}</div>
                                <div className="mt-1 text-blue-700">{event.message || event.status}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="grid gap-3 lg:grid-cols-3">
                        <Input
                          value={candidate.current_role}
                          onChange={(event) => patchCandidate(candidate.id, { current_role: event.target.value })}
                          placeholder="当前岗位"
                        />
                        <RegionSelect
                          className="lg:col-span-2"
                          value={candidate.location}
                          onChange={(location) => patchCandidate(candidate.id, { location })}
                        />
                        <Input
                          value={candidate.tags}
                          onChange={(event) => patchCandidate(candidate.id, { tags: event.target.value })}
                          placeholder="标签"
                        />
                        <select
                          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                          value={candidate.contact_status}
                          onChange={(event) =>
                            patchCandidate(candidate.id, {
                              contact_status: event.target.value as RecruitmentCandidate["contact_status"],
                            })
                          }
                        >
                          {CONTACT_STATUS_OPTIONS.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                        <select
                          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                          value={candidate.group_status}
                          onChange={(event) =>
                            patchCandidate(candidate.id, {
                              group_status: event.target.value as RecruitmentCandidate["group_status"],
                            })
                          }
                        >
                          {GROUP_STATUS_OPTIONS.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                        <div className="flex items-center gap-2 rounded-md border px-3">
                          <Checkbox
                            id={`candidate-consent-${candidate.id}`}
                            checked={candidate.consent_to_contact}
                            onCheckedChange={(value) =>
                              patchCandidate(candidate.id, { consent_to_contact: Boolean(value) })
                            }
                          />
                          <Label htmlFor={`candidate-consent-${candidate.id}`} className="text-sm">
                            已同意留资
                          </Label>
                        </div>
                      </div>

                      <div className="grid gap-3 lg:grid-cols-2">
                        <Textarea
                          className="min-h-24"
                          value={candidate.profile}
                          onChange={(event) => patchCandidate(candidate.id, { profile: event.target.value })}
                          placeholder="资料摘要"
                        />
                        <Textarea
                          className="min-h-24"
                          value={candidate.last_message}
                          onChange={(event) => patchCandidate(candidate.id, { last_message: event.target.value })}
                          placeholder="最近沟通"
                        />
                        <Input
                          value={candidate.private_contact}
                          onChange={(event) => patchCandidate(candidate.id, { private_contact: event.target.value })}
                          placeholder="候选人同意后填写联系方式"
                        />
                        <Input
                          value={candidate.next_action}
                          onChange={(event) => patchCandidate(candidate.id, { next_action: event.target.value })}
                          placeholder="下一步动作"
                        />
                      </div>

                      {/* AI 话术面板 */}
                      <div className="mt-3">
                        <AIDraftPanel
                          requirementId={selectedRequirementId!}
                          candidateId={candidate.id}
                          candidateName={candidate.name}
                          lastMessage={candidate.last_message}
                          currentRole={candidate.current_role}
                          draft={chatDrafts[candidate.id] || null}
                          generating={generatingChatDraftId === candidate.id}
                          onGenerateStart={() => setGeneratingChatDraftId(candidate.id)}
                          onDraftGenerated={(result) => handleChatDraftGenerated(candidate.id, result)}
                          onGenerateComplete={() => setGeneratingChatDraftId(null)}
                        />
                      </div>

                      {draft && (
                        <div className="mt-3 rounded-md border bg-muted/30 p-3">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <div className="text-sm font-medium">首轮话术（旧版）</div>
                            <Button variant="outline" size="sm" onClick={() => void handleCopy(draft)}>
                              <Clipboard className="mr-2 h-4 w-4" />
                              复制
                            </Button>
                          </div>
                          <div className="whitespace-pre-wrap text-sm leading-6 text-foreground">{draft}</div>
                        </div>
                      )}

                      <div className="rounded-md border p-3">
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <div className="text-sm font-medium">沟通时间线</div>
                          <Badge variant="outline">{timeline.length}</Badge>
                        </div>
                        <div className="max-h-56 space-y-2 overflow-auto pr-1">
                          {timeline.length === 0 ? (
                            <div className="rounded-md bg-muted/30 px-3 py-4 text-center text-sm text-muted-foreground">
                              暂无沟通记录
                            </div>
                          ) : (
                            timeline.slice(0, 8).map((event) => (
                              <div key={event.id} className="grid gap-2 rounded-md bg-muted/30 p-3 text-sm sm:grid-cols-[96px_minmax(0,1fr)]">
                                <div className="space-y-1 text-xs text-muted-foreground">
                                  <div>{formatTimelineTime(event.created_at)}</div>
                                  <Badge variant="outline" className="bg-background">
                                    {eventTypeLabel(event.event_type)}
                                  </Badge>
                                </div>
                                <div className="min-w-0">
                                  <div className="font-medium text-foreground">{event.title}</div>
                                  {event.content && (
                                    <div className="mt-1 whitespace-pre-wrap break-words text-muted-foreground">
                                      {event.content}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                          <Textarea
                            className="min-h-16"
                            value={timelineDraft}
                            onChange={(event) =>
                              setTimelineDrafts((prev) => ({ ...prev, [candidate.id]: event.target.value }))
                            }
                            placeholder="记录BOSS回复、人工发送结果、跟进备注"
                          />
                          <Button
                            className="sm:self-end"
                            variant="outline"
                            onClick={() => void handleAddTimelineEvent(candidate.id)}
                            disabled={addingTimelineCandidateId === candidate.id || !timelineDraft.trim()}
                          >
                            {addingTimelineCandidateId === candidate.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Plus className="mr-2 h-4 w-4" />
                            )}
                            记录进展
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        </div>
      </div>
      </div>
    </div>
  );

  const majorDialog = (
    <Dialog open={majorDialogOpen} onOpenChange={setMajorDialogOpen}>
      <DialogContent className="max-w-5xl gap-0 p-0">
        <DialogHeader className="border-b px-6 py-4">
          <div className="flex items-center gap-4">
            <DialogTitle className="text-base">请选择专业</DialogTitle>
            <Input
              className="max-w-sm"
              value={majorSearch}
              onChange={(event) => setMajorSearch(event.target.value)}
              placeholder="搜索或输入专业名称"
            />
            {majorSearch.trim() && (
              <Button type="button" variant="outline" onClick={() => setMajorDraft(majorSearch.trim())}>
                使用输入
              </Button>
            )}
          </div>
        </DialogHeader>
        {majorSearch.trim() ? (
          <div className="h-[520px] overflow-auto text-sm">
            {majorSearchResults.length === 0 ? (
              <button
                type="button"
                className="flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted"
                onClick={() => setMajorDraft(majorSearch.trim())}
              >
                <Checkbox checked={majorDraft === majorSearch.trim()} />
                <span>使用“{majorSearch.trim()}”</span>
              </button>
            ) : (
              majorSearchResults.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={`flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted ${majorDraft === item.value ? "text-primary" : ""}`}
                  onClick={() => setMajorDraft(item.value)}
                >
                  <Checkbox checked={majorDraft === item.value} />
                  <span>{item.label}</span>
                </button>
              ))
            )}
          </div>
        ) : (
          <div className="grid h-[520px] grid-cols-3 overflow-hidden text-sm">
            <div className="overflow-auto border-r">
              {MAJOR_OPTIONS.map((category) => {
                const value = `${category.category}/全部`;
                const checked = majorDraft === value || majorDraft.startsWith(`${category.category}/`);
                return (
                  <button
                    key={category.category}
                    type="button"
                    className={`flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted ${majorCategory === category.category ? "bg-muted text-primary" : ""}`}
                    onClick={() => {
                      setMajorCategory(category.category);
                      setMajorGroup(category.groups[0].name);
                    }}
                  >
                    <Checkbox checked={checked} onCheckedChange={() => setMajorDraft(value)} onClick={(event) => event.stopPropagation()} />
                    <span className="flex-1">{category.category}</span>
                    <span className="text-muted-foreground">›</span>
                  </button>
                );
              })}
            </div>
            <div className="overflow-auto border-r">
              <button
                type="button"
                className="flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted"
                onClick={() => setMajorDraft(`${activeMajorCategory.category}/全部`)}
              >
                <Checkbox checked={majorDraft === `${activeMajorCategory.category}/全部`} />
                <span>全部</span>
              </button>
              {activeMajorCategory.groups.map((group) => {
                const value = `${activeMajorCategory.category}/${group.name}/全部`;
                const checked = majorDraft === value || majorDraft.startsWith(`${activeMajorCategory.category}/${group.name}/`);
                return (
                  <button
                    key={`${activeMajorCategory.category}-${group.name}`}
                    type="button"
                    className={`flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted ${majorGroup === group.name ? "bg-muted text-primary" : ""}`}
                    onClick={() => setMajorGroup(group.name)}
                  >
                    <Checkbox checked={checked} onCheckedChange={() => setMajorDraft(value)} onClick={(event) => event.stopPropagation()} />
                    <span className="flex-1">{group.name}</span>
                    {group.majors.length > 0 && <span className="text-muted-foreground">›</span>}
                  </button>
                );
              })}
            </div>
            <div className="overflow-auto">
              <button
                type="button"
                className="flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted"
                onClick={() => setMajorDraft(`${activeMajorCategory.category}/${activeMajorGroup.name}/全部`)}
              >
                <Checkbox checked={majorDraft === `${activeMajorCategory.category}/${activeMajorGroup.name}/全部`} />
                <span>全部</span>
              </button>
              {activeMajorGroup.majors.map((major) => {
                const value = `${activeMajorCategory.category}/${activeMajorGroup.name}/${major}`;
                return (
                  <button
                    key={value}
                    type="button"
                    className={`flex w-full items-center gap-3 px-6 py-4 text-left hover:bg-muted ${majorDraft === value ? "text-primary" : ""}`}
                    onClick={() => setMajorDraft(value)}
                  >
                    <Checkbox checked={majorDraft === value} />
                    <span>{major}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
        <DialogFooter className="border-t px-6 py-4">
          <Button type="button" variant="outline" onClick={() => {
            setMajorDraft("");
            setMajorSearch("");
          }}>
            重置
          </Button>
          <Button type="button" variant="outline" onClick={() => setMajorDialogOpen(false)}>
            取消
          </Button>
          <Button type="button" onClick={confirmMajorDialog}>
            确定
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const deleteAllDialog = (
    <Dialog
      open={deleteAllDialogOpen}
      onOpenChange={(open) => {
        setDeleteAllDialogOpen(open);
        if (!open) setDeleteAllPassword("");
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>确认删除全部需求</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">该操作会删除所有招聘需求、候选人和沟通记录。请输入当前账号密码进行二次确认。</p>
          <div className="space-y-2">
            <Label htmlFor="delete-all-password">当前账号密码</Label>
            <Input
              id="delete-all-password"
              type="password"
              value={deleteAllPassword}
              onChange={(event) => setDeleteAllPassword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleDeleteAllRequirements();
              }}
              placeholder="请输入当前登录账号密码"
              autoComplete="current-password"
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setDeleteAllDialogOpen(false)}>
            取消
          </Button>
          <Button type="button" variant="destructive" onClick={() => void handleDeleteAllRequirements()} disabled={deletingAllRequirements}>
            {deletingAllRequirements && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            确认删除全部
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  if (embedded) {
    return (
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {headerContent}
        {mainContent}
        {majorDialog}
        {deleteAllDialog}
      </div>
    );
  }

  return (
    <>
      <ResponsiveLayout header={headerContent} main={mainContent} />
      {majorDialog}
      {deleteAllDialog}
    </>
  );
}
