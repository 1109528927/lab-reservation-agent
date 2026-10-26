import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    {
      path: '/m',
      component: () => import('@/layouts/MobileLayout.vue'),
      redirect: '/m/home',
      children: [
        { path: 'home', name: 'MHome', component: () => import('@/views/mobile/Home.vue') },
        {
          path: 'reserve',
          name: 'MReserve',
          component: () => import('@/views/mobile/Reserve.vue')
        },
        { path: 'pass', name: 'MPass', component: () => import('@/views/mobile/Pass.vue') },
        { path: 'messages', name: 'MMessages', component: () => import('@/views/mobile/Messages.vue') },
        { path: 'repair', name: 'MRepair', component: () => import('@/views/mobile/Repair.vue') },
        { path: 'agent', name: 'MAgent', component: () => import('@/views/mobile/Agent.vue') },
        { path: 'scan', name: 'MScan', component: () => import('@/views/mobile/Scan.vue') },
        { path: 'mine', name: 'MMine', component: () => import('@/views/mobile/Mine.vue') }
      ]
    },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layout.vue'),
      children: [
        { path: 'home', name: 'Home', component: () => import('@/views/Home.vue') },
        { path: 'lab', name: 'Lab', component: () => import('@/views/manager/Lab.vue') },
        {
          path: 'schedule',
          name: 'Schedule',
          component: () => import('@/views/manager/Schedule.vue')
        },
        {
          path: 'reservation',
          name: 'Reservation',
          component: () => import('@/views/manager/Reservation.vue')
        },

        {
          path: 'access',
          name: 'Access',
          component: () => import('@/views/manager/AccessSim.vue')
        },
        {
          path: 'agent',
          name: 'Agent',
          component: () => import('@/views/manager/AgentChat.vue')
        },
        {
          path: 'messages',
          name: 'MgrMessages',
          component: () => import('@/views/manager/Messages.vue')
        },
        {
          path: 'repair',
          name: 'MgrRepair',
          component: () => import('@/views/manager/RepairAdmin.vue')
        },
        {
          path: 'credit',
          name: 'MgrCredit',
          component: () => import('@/views/manager/CreditAdmin.vue')
        }
      ]
    }
  ]
})

export default router
