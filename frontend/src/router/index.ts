import { createRouter, createWebHistory } from 'vue-router'
import LevelSelect from '@/views/LevelSelect.vue'
import Workspace from '@/views/Workspace.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/',          name: 'level-select', component: LevelSelect },
    { path: '/workspace', name: 'workspace',    component: Workspace   },
  ],
})

export default router
