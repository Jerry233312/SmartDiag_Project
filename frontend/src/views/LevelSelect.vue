<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex flex-col">

    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <header class="pt-10 pb-6 text-center px-6 relative">
      <!-- Reset button — top right -->
      <button
        class="absolute top-6 right-6 flex items-center gap-1.5 text-[11px] font-semibold text-rose-400 border border-rose-500/40 hover:border-rose-400 hover:bg-rose-500/10 px-3 py-1.5 rounded-full transition-all"
        @click="handleReset"
      >
        🔄 重置题库与进度
      </button>

      <div class="inline-flex items-center gap-3 mb-1">
        <span class="text-5xl drop-shadow-lg">🩺</span>
        <h1 class="text-4xl font-black text-white tracking-tight drop-shadow">智诊 SmartDiag</h1>
      </div>
      <p class="text-indigo-300 text-sm mt-2 font-medium">选择关卡，开始你的医疗实训挑战</p>
      <div class="mt-4 flex items-center justify-center gap-2 text-[11px] text-indigo-400/70 font-medium">
        <span class="w-16 h-px bg-indigo-700"></span>
        <span>乡村医生 AI 实训平台</span>
        <span class="w-16 h-px bg-indigo-700"></span>
      </div>
    </header>

    <!-- ── Level Cards ───────────────────────────────────────────────────────── -->
    <main class="flex-1 px-6 pb-16 max-w-2xl mx-auto w-full">

      <!-- Loading -->
      <div v-if="loadingCases" class="flex flex-col items-center justify-center py-24 text-indigo-400/60">
        <svg class="w-8 h-8 animate-spin mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
        <p class="text-sm">正在从服务器获取关卡数据…</p>
      </div>

      <!-- Backend error -->
      <div v-else-if="loadError" class="flex flex-col items-center justify-center py-24 text-center space-y-4">
        <span class="text-4xl">⚠️</span>
        <p class="text-red-400 text-sm max-w-xs">{{ loadError }}</p>
        <button
          class="px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 transition"
          @click="fetchCases"
        >重试连接</button>
        <p class="text-indigo-600/60 text-[11px]">请先双击 start_game.bat 启动后端</p>
      </div>

      <!-- 5 Level cards -->
      <div v-else class="space-y-4">
        <LevelCard
          v-for="def in LEVEL_DEFS"
          :key="def.level"
          :levelDef="def"
          :drawnCase="drawnCases[def.level]"
          :locked="isLocked(def.level)"
          @click="startLevel(def.level)"
        />
      </div>

    </main>

    <!-- ── Footer ──────────────────────────────────────────────────────────── -->
    <footer class="text-center text-[11px] text-indigo-600 pb-6">
      Powered by 腾讯云 LKE &nbsp;·&nbsp; SmartDiag v3.0
    </footer>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineComponent, h } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── localStorage key ─────────────────────────────────────────────────────────
// 存储已解锁的等级数组，如 [1, 2, 3]（与 Workspace.vue 共享同一 key）
const STORAGE_KEY = 'smartdiag_unlocked_levels'

// ─── 五阶关卡定义 ──────────────────────────────────────────────────────────────
interface LevelDef {
  level: number
  label: string
  desc: string
  icon: string
  colorKey: 'emerald' | 'amber' | 'orange' | 'red' | 'purple'
}

const LEVEL_DEFS: LevelDef[] = [
  { level: 1, label: '助理医师实训',   desc: '基础问诊入门，掌握常见慢病诊断要点',         icon: '🌿', colorKey: 'emerald' },
  { level: 2, label: '住院医师晋阶',   desc: '病情分析进阶，处理并发症与用药调整',         icon: '🔥', colorKey: 'amber'   },
  { level: 3, label: '主治医师挑战',   desc: '多因素综合管理，鉴别复杂病情',               icon: '⚡', colorKey: 'orange'  },
  { level: 4, label: '副主任医师考核', desc: '疑难病例分析，多科联合决策',                 icon: '💫', colorKey: 'red'     },
  { level: 5, label: '主任医师巅峰',   desc: '极限挑战，顶级临床思维博弈',                 icon: '🏆', colorKey: 'purple'  },
]

// ─── 从后端拉取的随机病例（每个等级一条）────────────────────────────────────────
interface DrawnCase { id: string; title: string; level: number; initial_budget: number }

const drawnCases   = ref<Record<number, DrawnCase | null>>({})
const loadingCases = ref(false)
const loadError    = ref('')

async function fetchCases() {
  loadingCases.value = true
  loadError.value    = ''
  try {
    const res = await fetch('http://localhost:28080/api/cases')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const all: DrawnCase[] = await res.json()
    // 按等级分组，每组随机取一条
    const drawn: Record<number, DrawnCase | null> = {}
    for (let lv = 1; lv <= 5; lv++) {
      const pool = all.filter(c => c.level === lv)
      drawn[lv] = pool.length
        ? pool[Math.floor(Math.random() * pool.length)]
        : null
    }
    drawnCases.value = drawn
  } catch (e) {
    loadError.value = `无法连接到后端：${(e as Error).message}`
  } finally {
    loadingCases.value = false
  }
}

// ─── 解锁状态 ─────────────────────────────────────────────────────────────────
const unlockedLevels = ref<number[]>([1])

function loadUnlocked(): number[] {
  try {
    const raw    = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : null
    return Array.isArray(parsed) && (parsed as number[]).length > 0
      ? (parsed as number[])
      : [1]
  } catch {
    return [1]
  }
}

onMounted(async () => {
  unlockedLevels.value = loadUnlocked()
  await fetchCases()
})

function isLocked(level: number): boolean {
  return !unlockedLevels.value.includes(level)
}

// ─── Actions ──────────────────────────────────────────────────────────────────
function startLevel(level: number) {
  if (isLocked(level)) return
  const drawn = drawnCases.value[level]
  if (!drawn) {
    alert(`Level ${level} 暂无可用病例。\n请在 Word 题库中添加对应案例后重新运行 data_parser.py。`)
    return
  }
  router.push({ path: '/workspace', query: { case_id: drawn.id, user_id: '1' } })
}

function handleReset() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([1]))
  location.reload()
}

// ─── LevelCard 子组件 ──────────────────────────────────────────────────────────
const COLORS = {
  emerald: { border: 'border-emerald-500/30', hoverBorder: 'hover:border-emerald-400/60', star: 'text-emerald-400', badge: 'bg-emerald-900/30 text-emerald-300' },
  amber:   { border: 'border-amber-500/30',   hoverBorder: 'hover:border-amber-400/60',   star: 'text-amber-400',   badge: 'bg-amber-900/30 text-amber-300'     },
  orange:  { border: 'border-orange-500/30',  hoverBorder: 'hover:border-orange-400/60',  star: 'text-orange-400',  badge: 'bg-orange-900/30 text-orange-300'   },
  red:     { border: 'border-red-500/30',     hoverBorder: 'hover:border-red-400/60',     star: 'text-red-400',     badge: 'bg-red-900/30 text-red-300'         },
  purple:  { border: 'border-purple-500/30',  hoverBorder: 'hover:border-purple-400/60',  star: 'text-purple-400',  badge: 'bg-purple-900/30 text-purple-300'   },
} as const

const LevelCard = defineComponent({
  props: {
    levelDef:  Object as () => LevelDef,
    drawnCase: Object as () => DrawnCase | null | undefined,
    locked:    Boolean,
  },
  emits: ['click'],
  setup(props, { emit }) {
    return () => {
      const def     = props.levelDef!
      const drawn   = props.drawnCase ?? null
      const locked  = props.locked ?? false
      const noCase  = !drawn
      const colors  = COLORS[def.colorKey]
      const stars   = '★'.repeat(def.level) + '☆'.repeat(5 - def.level)

      const borderClass = (locked || noCase)
        ? 'border-white/5'
        : `${colors.border} ${colors.hoverBorder}`

      return h('button', {
        disabled: locked || noCase,
        class: [
          'relative w-full text-left rounded-2xl border bg-white/5 backdrop-blur-sm p-5',
          'transition-all duration-200',
          (locked || noCase)
            ? 'opacity-40 cursor-not-allowed'
            : 'hover:bg-white/10 hover:shadow-xl hover:shadow-black/30 hover:-translate-y-0.5 active:scale-[0.99]',
          borderClass,
        ].join(' '),
        onClick: () => !(locked || noCase) && emit('click'),
      }, [

        /* Top row: level badge + status badge */
        h('div', { class: 'flex items-center justify-between mb-4' }, [
          h('span', { class: `text-[11px] font-bold px-2.5 py-1 rounded-full ${colors.badge}` },
            `Level ${def.level} · ${def.label}`
          ),
          noCase
            ? h('span', { class: 'text-[10px] text-amber-400/70 flex items-center gap-1' }, [h('span', '⚠️'), h('span', '暂无案例')])
            : locked
              ? h('span', { class: 'text-[10px] text-white/30 flex items-center gap-1' }, [h('span', '🔒'), h('span', '待解锁')])
              : h('span', { class: 'text-[10px] text-emerald-400/60 flex items-center gap-1' }, [h('span', '✅'), h('span', '已解锁')]),
        ]),

        /* Icon + Case title (or level desc if no case) */
        h('div', { class: 'flex items-start gap-3 mb-3' }, [
          h('span', { class: 'text-3xl flex-shrink-0 mt-0.5' }, def.icon),
          h('div', { class: 'min-w-0' }, [
            h('h3', { class: 'text-base font-bold text-white leading-tight' },
              drawn ? drawn.title : def.desc
            ),
            drawn
              ? h('p', { class: 'text-[11px] text-white/40 mt-0.5 leading-snug' }, def.desc)
              : h('p', { class: 'text-[11px] text-amber-400/50 mt-1 italic' }, '请先补充 Word 题库并重新运行 data_parser.py'),
          ]),
        ]),

        /* Stars */
        h('p', { class: `text-sm font-bold mb-3 ${colors.star}` }, stars),

        /* Footer: case id + budget */
        drawn
          ? h('div', { class: 'flex items-center justify-between' }, [
              h('span', { class: 'text-[10px] text-white/25 font-medium' }, `案例 ${drawn.id}`),
              h('span', { class: 'text-[11px] text-indigo-400 font-bold flex items-center gap-1' }, [
                h('span', '🪙'), h('span', `${drawn.initial_budget} 金币`),
              ]),
            ])
          : null,

      ])
    }
  },
})
</script>
