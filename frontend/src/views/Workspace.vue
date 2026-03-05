<template>

  <!-- ── Mount loading / error ─────────────────────────────────────────── -->
  <div
    v-if="initializing || initMountError"
    class="flex h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900"
  >
    <div class="text-center space-y-4">
      <template v-if="initializing">
        <svg class="w-10 h-10 animate-spin text-indigo-400 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
        <p class="text-indigo-300 text-sm">正在初始化问诊会话…</p>
      </template>
      <template v-else>
        <span class="text-4xl">⚠️</span>
        <p class="text-red-400 text-sm">{{ initMountError }}</p>
        <button class="px-6 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 transition" @click="router.push('/')">← 返回关卡选择</button>
      </template>
    </div>
  </div>

  <!-- ── Main Workspace ─────────────────────────────────────────────────── -->
  <div v-else class="flex h-screen bg-gray-50 overflow-hidden font-sans antialiased">

    <!-- ─── Left Panel ──────────────────────────────────────────────────── -->
    <aside class="w-[340px] flex-shrink-0 flex flex-col bg-white border-r border-gray-200/80 shadow-sm">

      <!-- Brand Header -->
      <div class="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
        <div class="min-w-0">
          <h1 class="text-sm font-bold text-gray-800 truncate">智诊 SmartDiag</h1>
          <p class="text-[11px] text-gray-400 mt-0.5 truncate">正在接诊：案例 {{ route.query.case_id ?? '—' }} 号未知患者</p>
        </div>
        <div class="flex items-center gap-1.5 ml-2 flex-shrink-0">
          <span class="text-[11px] bg-indigo-50 text-indigo-600 font-semibold px-2 py-1 rounded-full border border-indigo-100">进行中</span>
          <button
            class="text-[11px] text-gray-400 hover:text-red-500 hover:bg-red-50 border border-gray-200 hover:border-red-200 px-2 py-1 rounded-full transition-all whitespace-nowrap"
            @click="handleExit"
          >🚪 退出</button>
        </div>
      </div>

      <!-- Budget Card -->
      <div class="mx-4 mt-4 rounded-2xl bg-gradient-to-br from-indigo-600 to-blue-500 p-4 shadow-lg shadow-indigo-200/50 flex-shrink-0">
        <p class="text-xs font-semibold text-indigo-200 uppercase tracking-widest">剩余金币</p>
        <div class="flex items-baseline gap-1.5 mt-1">
          <span class="text-4xl font-black text-white tabular-nums">{{ store.budgetLeft }}</span>
          <span class="text-sm text-indigo-200">🪙</span>
        </div>
        <div class="mt-3 h-1.5 bg-white/20 rounded-full overflow-hidden">
          <div class="h-full bg-white rounded-full transition-all duration-700 ease-out" :style="{ width: `${store.budgetPercent}%` }"/>
        </div>
        <p class="text-[10px] text-indigo-200/70 mt-1.5 text-right">初始 {{ store.initialBudget }} 🪙 金币</p>
      </div>

      <!-- Scrollable Middle -->
      <div class="flex-1 overflow-y-auto px-4 pb-2 space-y-4 mt-4 scrollbar-thin">

        <!-- Instruments Grid -->
        <div>
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">器械检查</p>
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="ins in INSTRUMENTS"
              :key="ins.action"
              class="flex flex-col items-center gap-1 p-2.5 rounded-xl border border-gray-100 bg-gray-50 hover:bg-indigo-50 hover:border-indigo-300 active:scale-95 transition-all duration-150 group disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="store.isLoading || !store.isInitialised"
              :title="`${ins.label} — 消耗 ${ins.cost} 金币`"
              @click="handleInstrument(ins.action)"
            >
              <span class="text-xl leading-none">{{ ins.icon }}</span>
              <span class="text-[10px] font-medium text-gray-500 group-hover:text-indigo-700 text-center leading-tight">{{ ins.label }}</span>
              <span class="text-[9px] text-amber-500 font-semibold">-{{ ins.cost }}🪙</span>
            </button>
          </div>
        </div>

        <!-- ── Collapsible Doctor Notes ──────────────────────────────────── -->
        <div class="rounded-2xl border border-gray-200 overflow-hidden">
          <!-- Accordion Header -->
          <button
            class="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
            @click="notesCollapsed = !notesCollapsed"
          >
            <span class="text-[12px] font-bold text-gray-600">📝 门诊病历本</span>
            <span class="text-gray-400 text-[10px] font-medium flex items-center gap-1">
              {{ notesCollapsed ? '展开填写' : '收起' }}
              <svg
                class="w-3.5 h-3.5 transition-transform duration-200"
                :class="{ 'rotate-180': !notesCollapsed }"
                xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
              >
                <path fill-rule="evenodd" d="M12.53 16.28a.75.75 0 01-1.06 0l-7.5-7.5a.75.75 0 011.06-1.06L12 14.69l6.97-6.97a.75.75 0 111.06 1.06l-7.5 7.5z" clip-rule="evenodd"/>
              </svg>
            </span>
          </button>

          <!-- Accordion Body -->
          <Transition name="accordion">
            <div v-show="!notesCollapsed" class="border-t border-gray-100 px-4 py-3 space-y-3 bg-white">

              <!-- Basic Info Row -->
              <div class="grid grid-cols-3 gap-2">
                <div>
                  <label class="block text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">姓名</label>
                  <input
                    v-model="notes.name"
                    type="text"
                    placeholder="患者姓名"
                    class="w-full text-[12px] text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-300 transition"
                  />
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">性别</label>
                  <input
                    v-model="notes.gender"
                    type="text"
                    placeholder="男 / 女"
                    class="w-full text-[12px] text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-300 transition"
                  />
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">年龄</label>
                  <input
                    v-model="notes.age"
                    type="text"
                    placeholder="岁"
                    class="w-full text-[12px] text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-300 transition"
                  />
                </div>
              </div>

              <div v-for="field in NOTE_FIELDS" :key="field.key">
                <label class="block text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">{{ field.label }}</label>
                <textarea
                  v-model="notes[field.key as keyof typeof notes]"
                  :rows="field.rows"
                  :placeholder="field.placeholder"
                  class="w-full text-[12px] text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-300 transition leading-relaxed"
                />
              </div>
              <!-- Fill indicator -->
              <div class="flex items-center gap-1.5 pt-1">
                <div
                  v-for="field in NOTE_FIELDS"
                  :key="field.key"
                  class="flex-1 h-1 rounded-full transition-colors"
                  :class="notes[field.key as keyof typeof notes].trim() ? 'bg-indigo-400' : 'bg-gray-200'"
                  :title="field.label"
                />
              </div>
            </div>
          </Transition>
        </div>

        <!-- Instrument Logs -->
        <div v-if="store.instrumentLogs.length > 0">
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">检查结果</p>
          <TransitionGroup name="log-slide" tag="div" class="space-y-2">
            <div
              v-for="log in store.instrumentLogs"
              :key="log.id"
              class="rounded-xl bg-gray-50 border border-gray-100 p-3 hover:border-gray-200 transition-colors"
            >
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs font-bold text-indigo-600">{{ log.action_name }}</span>
                <span class="text-[10px] font-semibold text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded-md">-{{ log.cost }}🪙</span>
              </div>
              <p class="text-[11px] text-gray-600 leading-relaxed">{{ log.result_text }}</p>
            </div>
          </TransitionGroup>
        </div>
        <div v-else class="flex flex-col items-center justify-center py-4 text-gray-300">
          <span class="text-3xl mb-1">🔬</span>
          <p class="text-xs">暂无检查结果</p>
        </div>

      </div>

      <!-- ── Submit / Review (fixed bottom) ────────────────────────────── -->
      <div class="px-4 pb-4 pt-3 border-t border-gray-100 bg-white flex-shrink-0">
        <!-- After submit: show review button only -->
        <div v-if="store.submitResult">
          <button
            class="w-full py-2.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-emerald-500 to-teal-500 shadow-md hover:from-emerald-400 hover:to-teal-400 active:scale-[0.98] transition-all"
            @click="showResultModal = true"
          >📊 查看考核评语</button>
        </div>

        <!-- Before submit: dynamic per-question answer form -->
        <template v-else>
          <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">考核作答</p>

          <!-- 每道题：题目 + 作答框 -->
          <div
            v-for="(question, idx) in store.caseQuestions"
            :key="idx"
            class="mb-3"
          >
            <p class="text-xs font-semibold text-indigo-700 mb-1 leading-snug">{{ question }}</p>
            <textarea
              v-model="questionAnswers[idx]"
              rows="2"
              :placeholder="`请回答第 ${idx + 1} 题...`"
              class="w-full text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-300 transition leading-relaxed"
            />
          </div>

          <!-- 兜底：没有题目时显示通用诊断框 -->
          <div v-if="!store.caseQuestions.length" class="mb-3">
            <p class="text-xs font-semibold text-indigo-700 mb-1">最终诊断</p>
            <textarea
              v-model="questionAnswers[0]"
              rows="2"
              placeholder="请输入您的最终诊断结论..."
              class="w-full text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-300 transition leading-relaxed"
            />
          </div>

          <button
            class="mt-1 w-full py-2.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-indigo-600 to-blue-500 shadow-md shadow-indigo-200/60 hover:from-indigo-500 hover:to-blue-400 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!hasAnyAnswer || store.isLoading"
            @click="handleSubmit"
          >
            <span v-if="store.isLoading" class="flex items-center justify-center gap-2">
              <svg class="w-3.5 h-3.5 animate-spin shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              AI 考官正在深度阅卷中，预计需要 20-30 秒，请稍候...
            </span>
            <span v-else>提交考核 →</span>
          </button>
        </template>
      </div>

    </aside>

    <!-- ─── Right Panel — Chat ───────────────────────────────────────────── -->
    <main class="flex-1 flex flex-col min-w-0">

      <!-- Chat Header -->
      <div class="flex items-center gap-3 px-6 py-3.5 bg-white border-b border-gray-200/80 shadow-sm">
        <div class="relative">
          <div class="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white font-bold text-sm shadow-md">患</div>
          <span class="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-400 border-2 border-white rounded-full"></span>
        </div>
        <div>
          <p class="text-sm font-semibold text-gray-800">虚拟患者</p>
          <p class="text-[11px] text-green-500 font-medium flex items-center gap-1">
            <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
            在线问诊中
          </p>
        </div>
        <div class="ml-auto text-[11px] text-gray-400">
          <span class="font-medium text-amber-500">🪙 {{ store.budgetLeft }}</span>
          <span class="text-gray-300 mx-1">/</span>
          <span>{{ store.initialBudget }} 金币</span>
        </div>
      </div>

      <!-- Messages Area -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto px-6 py-5 scroll-smooth"
        style="background: radial-gradient(ellipse at top, #eef2ff 0%, #f8fafc 60%)"
      >
        <!-- Empty State -->
        <div v-if="store.messages.length === 0" class="flex flex-col items-center justify-center h-full select-none">
          <div class="text-6xl mb-4 opacity-40">💬</div>
          <p class="text-sm text-gray-400 font-medium">向患者发送第一条消息，开始问诊</p>
          <p class="text-xs text-gray-300 mt-1">尽量收集足够信息后再提交诊断</p>
        </div>

        <!-- Message Bubbles — only render non-empty messages to avoid ghost bubbles -->
        <TransitionGroup name="msg-pop" tag="div" class="space-y-5">
          <template v-for="msg in store.messages" :key="msg.id">
            <div
              v-if="msg.content.trim() !== ''"
              :class="['flex items-end gap-2.5', msg.role === 'doctor' ? 'flex-row-reverse' : 'flex-row']"
            >
              <div :class="['w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0 shadow-sm', msg.role === 'doctor' ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white' : 'bg-gradient-to-br from-emerald-400 to-teal-500 text-white']">
                {{ msg.role === 'doctor' ? '医' : '患' }}
              </div>
              <div :class="['relative max-w-[72%] px-4 py-3 text-sm leading-relaxed shadow-sm', msg.role === 'doctor' ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white rounded-2xl rounded-br-sm' : 'bg-white text-gray-800 border border-gray-100 rounded-2xl rounded-bl-sm']">
                <!-- Streaming blink cursor on the last assistant message -->
                <span
                  v-if="isStreaming && msg === store.messages[store.messages.length - 1] && msg.role === 'assistant'"
                  class="after:content-['▍'] after:ml-0.5 after:animate-blink after:text-gray-400"
                >{{ msg.content }}</span>
                <span v-else>{{ msg.content }}</span>
                <span :class="['block text-[9px] mt-1.5 select-none', msg.role === 'doctor' ? 'text-indigo-200 text-right' : 'text-gray-300']">{{ formatTime(msg.timestamp) }}</span>
              </div>
            </div>
          </template>
        </TransitionGroup>

        <!-- Streaming loading dots (empty placeholder phase) -->
        <div
          v-if="isStreaming && store.messages[store.messages.length - 1]?.content === ''"
          class="flex items-end gap-2.5 mt-5"
        >
          <div class="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-[11px] font-bold text-white shadow-sm">患</div>
          <div class="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
            <span class="flex gap-1 items-center h-4">
              <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]"></span>
              <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]"></span>
              <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]"></span>
            </span>
          </div>
        </div>
      </div>

      <!-- Toast error -->
      <Transition name="toast">
        <div
          v-if="chatError"
          class="mx-6 bg-red-50 border border-red-200 text-red-600 text-xs px-4 py-2.5 rounded-xl flex items-center gap-2"
        >
          <svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          {{ chatError }}
        </div>
      </Transition>

      <!-- Input Area -->
      <div class="px-4 py-4 bg-white border-t border-gray-100">
        <div class="flex items-end gap-3 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
          <textarea
            ref="inputRef"
            v-model="inputMessage"
            rows="1"
            placeholder="向患者提问… (Enter 发送，Shift+Enter 换行)"
            class="flex-1 bg-transparent text-sm text-gray-800 resize-none focus:outline-none placeholder:text-gray-300 max-h-28 leading-relaxed"
            :disabled="isStreaming"
            @keydown="handleInputKeydown"
            @input="autoResize"
          />
          <button
            class="w-9 h-9 flex-shrink-0 rounded-xl bg-gradient-to-br from-indigo-600 to-blue-500 text-white flex items-center justify-center shadow-md hover:shadow-indigo-300/60 hover:scale-105 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
            :disabled="!inputMessage.trim() || isStreaming"
            @click="handleSendMessage"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z"/>
            </svg>
          </button>
        </div>
      </div>

    </main>

    <!-- ─── Result Modal ──────────────────────────────────────────────────── -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showResultModal"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
          style="background: rgba(0,0,0,0.6); backdrop-filter: blur(8px)"
          @click.self="showResultModal = false"
        >
          <div class="modal-card relative bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[92vh] overflow-y-auto">
            <div class="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-indigo-500 via-blue-400 to-teal-400 rounded-t-3xl"></div>

            <!-- ❌ Close button -->
            <button
              class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all text-sm z-10"
              @click="showResultModal = false"
            >✕</button>

            <div class="p-8 pt-6">

              <!-- ── Block 1: Score ── -->
              <div class="text-center mb-6">
                <div class="text-5xl mb-2">{{ scoreEmoji }}</div>
                <h2 class="text-xl font-bold text-gray-800">考核结果</h2>
                <p class="text-sm text-gray-400 mt-0.5">本次诊断评分</p>
                <div class="relative inline-flex items-center justify-center my-5">
                  <svg class="w-32 h-32 -rotate-90" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="52" fill="none" stroke="#e5e7eb" stroke-width="10"/>
                    <circle
                      cx="60" cy="60" r="52" fill="none"
                      stroke="url(#scoreGrad)" stroke-width="10"
                      stroke-linecap="round"
                      :stroke-dasharray="`${2 * Math.PI * 52}`"
                      :stroke-dashoffset="`${2 * Math.PI * 52 * (1 - (store.submitResult?.final_score ?? 0) / 100)}`"
                      style="transition: stroke-dashoffset 1.2s cubic-bezier(0.25,1,0.5,1)"
                    />
                    <defs>
                      <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#3b82f6"/>
                      </linearGradient>
                    </defs>
                  </svg>
                  <div class="absolute text-center">
                    <span class="text-4xl font-black text-indigo-600 tabular-nums">{{ store.submitResult?.final_score }}</span>
                    <span class="block text-xs text-gray-400 font-medium">/ 100</span>
                  </div>
                </div>
              </div>

              <!-- ── Unlock Banner ── -->
              <div v-if="justUnlockedNext" class="flex items-center gap-3 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-2xl px-4 py-3 mb-4">
                <span class="text-2xl">🎉</span>
                <div>
                  <p class="text-sm font-bold text-emerald-700">恭喜！您已成功解锁下一关！</p>
                  <p class="text-[11px] text-emerald-500 mt-0.5">返回关卡选择页即可挑战新关卡</p>
                </div>
              </div>

              <!-- ── Block 2: AI Evaluation ── -->
              <div class="bg-gray-50 rounded-2xl p-4 mb-4 border border-gray-100">
                <p class="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">🎓 AI 考官点评</p>
                <p class="text-sm text-gray-700 leading-relaxed">{{ store.submitResult?.evaluation }}</p>
              </div>

              <!-- ── Block 3: Standard Answer ── -->
              <div v-if="store.submitResult?.standard_answer_public" class="bg-emerald-50 rounded-2xl p-4 mb-6 border border-emerald-100">
                <p class="text-[11px] font-bold text-emerald-500 uppercase tracking-widest mb-3">✅ 官方标准答案（供复盘参考）</p>

                <div class="mb-3">
                  <p class="text-[10px] font-bold text-emerald-600 uppercase tracking-wide mb-1">标准诊断</p>
                  <p class="text-sm font-semibold text-gray-800">{{ store.submitResult.standard_answer_public.diagnosis ?? '—' }}</p>
                </div>

                <div class="mb-3">
                  <p class="text-[10px] font-bold text-emerald-600 uppercase tracking-wide mb-1.5">必查项目</p>
                  <div class="flex flex-wrap gap-1.5">
                    <span
                      v-for="inst in store.submitResult.standard_answer_public.required_instruments"
                      :key="inst"
                      class="text-[11px] bg-emerald-100 text-emerald-700 px-2.5 py-0.5 rounded-full font-medium"
                    >{{ inst }}</span>
                  </div>
                </div>

                <div v-if="Object.keys(store.submitResult.standard_answer_public.key_findings ?? {}).length > 0">
                  <p class="text-[10px] font-bold text-emerald-600 uppercase tracking-wide mb-1.5">考核要点</p>
                  <ul class="space-y-1.5">
                    <li v-for="(val, key) in store.submitResult.standard_answer_public.key_findings" :key="key" class="text-[11px] text-gray-600 leading-relaxed">
                      <span class="font-semibold text-emerald-700">{{ key }}：</span>{{ val }}
                    </li>
                  </ul>
                </div>
              </div>

              <!-- Buttons -->
              <div class="flex flex-col gap-2.5">
                <!-- Primary CTA: next level (score >= 60 and not last level) -->
                <button
                  v-if="canGoNextLevel"
                  class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-sm font-bold shadow-lg shadow-emerald-200/60 hover:from-emerald-400 hover:to-teal-400 transition active:scale-[0.98]"
                  @click="handleNextLevel"
                >🚀 进入下一关</button>
                <!-- Secondary actions -->
                <div class="flex gap-3">
                  <button
                    class="flex-1 py-2.5 rounded-xl border border-gray-200 text-gray-500 text-sm font-medium hover:bg-gray-50 transition active:scale-95"
                    @click="handleRestart"
                  >← 再选关卡</button>
                  <button
                    class="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-500 text-white text-sm font-semibold shadow-lg shadow-indigo-200/60 hover:from-indigo-500 hover:to-blue-400 transition active:scale-95"
                    @click="showResultModal = false"
                  >查看复盘</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConsultationStore } from '@/store/consultation'

// ─── Router & Store ───────────────────────────────────────────────────────────
const router = useRouter()
const route  = useRoute()
const store  = useConsultationStore()

// ─── Mount-time init ──────────────────────────────────────────────────────────
const initializing   = ref(false)
const initMountError = ref('')

onMounted(async () => {
  if (store.isInitialised) return
  const caseId = String(route.query.case_id || '')  // 绝不用 Number()，关卡 ID 是字符串
  const userId = route.query.user_id as string | undefined
  if (!caseId || !userId) { router.replace('/'); return }
  initializing.value = true
  try {
    await store.initConsultation({ case_id: caseId, user_id: userId })
  } catch (e) {
    initMountError.value = `初始化失败：${(e as Error).message}`
  } finally {
    initializing.value = false
  }
})

// ─── Instruments（仅血压 + 血糖）────────────────────────────────────────────────
const INSTRUMENTS = [
  { action: '血压测量', label: '血压', icon: '💓', cost: 20  },
  { action: '血糖检测', label: '血糖', icon: '💉', cost: 120 },
] as const

async function handleInstrument(actionName: string) {
  try { await store.callInstrument(actionName) }
  catch (e) { console.error('器械检查失败:', e) }
}

// ─── Structured Doctor Notes ──────────────────────────────────────────────────
const notesCollapsed = ref(true)

const notes = reactive({
  name:            '',
  gender:          '',
  age:             '',
  chiefComplaint:  '',
  presentIllness:  '',
  pastHistory:     '',
  personalHistory: '',
})

const NOTE_FIELDS = [
  { key: 'chiefComplaint',  label: '主诉',         rows: 2, placeholder: '患者的主要症状及持续时间，如：口渴多尿 3 个月…' },
  { key: 'presentIllness',  label: '现病史',        rows: 3, placeholder: '症状发展经过、伴随症状、诊疗经过…' },
  { key: 'pastHistory',     label: '既往史',        rows: 2, placeholder: '既往患病、手术、过敏史…' },
  { key: 'personalHistory', label: '个人 / 家族史', rows: 2, placeholder: '吸烟饮酒、家族遗传病史…' },
]

function formatNotes(): string {
  const parts: string[] = []
  const basicInfo = [
    notes.name.trim()   ? `姓名：${notes.name.trim()}`   : null,
    notes.gender.trim() ? `性别：${notes.gender.trim()}` : null,
    notes.age.trim()    ? `年龄：${notes.age.trim()}`    : null,
  ].filter(Boolean).join('  ')
  if (basicInfo) parts.push(`【患者基本信息】${basicInfo}`)
  if (notes.chiefComplaint.trim())  parts.push(`主诉：${notes.chiefComplaint.trim()}`)
  if (notes.presentIllness.trim())  parts.push(`现病史：${notes.presentIllness.trim()}`)
  if (notes.pastHistory.trim())     parts.push(`既往史：${notes.pastHistory.trim()}`)
  if (notes.personalHistory.trim()) parts.push(`个人/家族史：${notes.personalHistory.trim()}`)
  return parts.length ? parts.join('\n') : '（医生未填写门诊记录）'
}

// ─── Level Unlock（五阶体系：按 case_id 首字母推算当前等级）──────────────────────
// localStorage key 存储已解锁的等级数组，如 [1, 2]
const STORAGE_KEY = 'smartdiag_unlocked_levels'

const _PREFIX_LEVEL: Record<string, number> = { A: 1, B: 2, C: 3, D: 4, E: 5 }

const currentCaseId = computed(() => String(route.query.case_id || ''))
const justUnlockedNext = ref(false)

/** 完成当前关卡后，将下一等级写入 localStorage */
function unlockNextLevel(caseId: string): void {
  const prefix = caseId[0]?.toUpperCase() ?? ''
  const currentLevel = _PREFIX_LEVEL[prefix] ?? 0
  if (currentLevel === 0 || currentLevel >= 5) return   // E 级已是最高级
  const nextLevel = currentLevel + 1
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const unlocked: number[] = raw ? (JSON.parse(raw) as number[]) : [1]
    if (!unlocked.includes(nextLevel)) {
      unlocked.push(nextLevel)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(unlocked))
      justUnlockedNext.value = true
    }
  } catch {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([1, nextLevel]))
    justUnlockedNext.value = true
  }
}

// ─── Next Level Navigation ────────────────────────────────────────────────────
/** 得分 ≥ 60 且当前等级 < 5 时，显示"进入下一关"按钮 */
const canGoNextLevel = computed(() => {
  const score = store.submitResult?.final_score ?? 0
  const prefix = currentCaseId.value[0]?.toUpperCase() ?? ''
  const currentLevel = _PREFIX_LEVEL[prefix] ?? 0
  return score >= 60 && currentLevel > 0 && currentLevel < 5
})

/** 返回大厅——LevelSelect 会自动展示已解锁的下一个等级 */
function handleNextLevel() {
  showResultModal.value = false
  store.reset()
  router.push('/')
}

// ─── Diagnosis submit ─────────────────────────────────────────────────────────
const questionAnswers = ref<string[]>([])
const showResultModal = ref(false)

// 至少有一道题填写了答案才允许提交
const hasAnyAnswer = computed(() => questionAnswers.value.some(a => a?.trim()))

// 当题目列表变化时（换关卡）重置答案数组
watch(
  () => store.caseQuestions,
  (qs) => { questionAnswers.value = Array(qs.length).fill('') },
  { immediate: true },
)

/** 将玩家各题作答组装成结构化字符串发给后端 */
function assembleAnswers(): string {
  const questions = store.caseQuestions
  if (!questions.length) return questionAnswers.value[0]?.trim() ?? ''
  return questions
    .map((q, i) => `【问题${i + 1}】${q}\n【考生回答】${questionAnswers.value[i]?.trim() ?? '（未作答）'}`)
    .join('\n\n')
}

async function handleSubmit() {
  const assembled = assembleAnswers()
  if (!assembled) return
  justUnlockedNext.value = false
  try {
    await store.submitDiagnosis(assembled, formatNotes())
    const cId = currentCaseId.value
    if ((store.submitResult?.final_score ?? 0) >= 60 && cId) {
      unlockNextLevel(cId)
    }
    showResultModal.value = true
  } catch (e) {
    console.error('提交诊断失败:', e)
  }
}

function handleExit() {
  store.reset()
  router.push('/')
}

function handleRestart() {
  showResultModal.value = false
  store.reset()
  router.push('/')
}

const scoreEmoji = computed(() => {
  const s = store.submitResult?.final_score ?? 0
  if (s >= 90) return '🏆'
  if (s >= 75) return '🌟'
  if (s >= 60) return '👍'
  return '📝'
})

// ─── Chat / SSE ───────────────────────────────────────────────────────────────
const inputMessage      = ref('')
const inputRef          = ref<HTMLTextAreaElement | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const isStreaming        = ref(false)
const chatError          = ref('')

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function scrollToBottom() {
  await nextTick()
  messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
}

watch(() => store.messages.length, scrollToBottom)

function handleInputKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage() }
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 112)}px`
}

async function handleSendMessage() {
  const content = inputMessage.value.trim()
  if (!content || isStreaming.value || !store.isInitialised) return

  inputMessage.value = ''
  chatError.value    = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'

  store.addDoctorMessage(content)
  store.addAssistantPlaceholder()
  isStreaming.value = true
  await scrollToBottom()

  try {
    const response = await fetch('http://localhost:28080/api/consultation/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ record_id: store.recordId, doctor_message: content }),
    })
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(`服务器错误 ${response.status}${text ? `：${text}` : ''}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder('utf-8')
    let buffer = '', finished = false

    while (!finished) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk

      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''

      for (const event of events) {
        let dataStr = ''
        for (const line of event.split('\n')) {
          if (line.trim().startsWith('data:')) { dataStr = line.trim().slice(5).trim(); break }
        }
        if (!dataStr) continue
        if (dataStr === '[DONE]') { finished = true; break }
        try {
          const parsed = JSON.parse(dataStr) as { content: string }
          if (parsed.content) { store.appendToLastAssistant(parsed.content); await scrollToBottom() }
        } catch {
          console.warn('[SSE] JSON 解析失败，跳过:', dataStr)
        }
      }
    }
    reader.cancel().catch(() => {})

  } catch (e) {
    chatError.value = (e as Error).message
    store.appendToLastAssistant('\n\n[连接错误，请重试]')
    setTimeout(() => { chatError.value = '' }, 5000)
  } finally {
    isStreaming.value = false
    await scrollToBottom()
    await nextTick()
    inputRef.value?.focus()
  }
}
</script>

<style scoped>
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
.animate-blink { animation: blink 0.9s step-end infinite; }

/* Accordion */
.accordion-enter-active { transition: all 0.25s ease-out; }
.accordion-leave-active { transition: all 0.2s ease-in; }
.accordion-enter-from,
.accordion-leave-to     { opacity: 0; max-height: 0; }
.accordion-enter-to,
.accordion-leave-from   { opacity: 1; max-height: 400px; }

.log-slide-enter-active { transition: all 0.3s ease; }
.log-slide-leave-active { transition: all 0.2s ease; }
.log-slide-enter-from   { opacity: 0; transform: translateY(-8px); }
.log-slide-leave-to     { opacity: 0; transform: translateY(-8px); }

.msg-pop-enter-active { transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.msg-pop-leave-active { transition: all 0.15s ease; }
.msg-pop-enter-from   { opacity: 0; transform: translateY(12px) scale(0.97); }
.msg-pop-leave-to     { opacity: 0; }

.modal-enter-active,
.modal-leave-active  { transition: opacity 0.25s ease; }
.modal-enter-from,
.modal-leave-to      { opacity: 0; }
.modal-enter-active .modal-card,
.modal-leave-active .modal-card { transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.modal-enter-from .modal-card,
.modal-leave-to .modal-card     { transform: scale(0.88) translateY(24px); }

.toast-enter-active { transition: all 0.25s ease; }
.toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from,
.toast-leave-to     { opacity: 0; transform: translateY(8px); }
</style>
