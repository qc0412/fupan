// GSAP 动效：入场 reveal 指令（适度，不喧宾夺主）
import gsap from 'gsap'

const prefersReduced =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// v-reveal               -> 元素淡入+上浮
// v-reveal="{children:'tbody tr', stagger:0.03}" -> 对子元素错落入场
export const reveal = {
  mounted(el, binding) {
    el.style.opacity = ''
    if (prefersReduced) return
    const opt = binding.value || {}
    const { y = 14, delay = 0, duration = 0.5, children, stagger } = opt
    const targets = children ? el.querySelectorAll(children) : el
    if (children && targets.length === 0) return
    gsap.from(targets, {
      opacity: 0,
      y,
      duration,
      ease: 'power2.out',
      delay,
      stagger: stagger ?? (children ? 0.035 : 0),
      clearProps: 'opacity,transform',
    })
  },
}

export function registerAnim(app) {
  app.directive('reveal', reveal)
}
