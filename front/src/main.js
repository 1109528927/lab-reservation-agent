import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import '@/assets/css/global.css'
const app = createApp(App)
app.use(router)
app.use(ElementPlus, {
  locale: zhCn
}) // 全量；只要 Message 也可不 use，但样式仍要引入
app.mount('#app')
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
