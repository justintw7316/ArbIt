'use client'
import { useState, useEffect, useRef } from 'react'

export function useCounter(target: number, duration = 1200) {
  const [value, setValue] = useState(target)
  const prevRef = useRef(target)
  const rafRef = useRef<number>()

  useEffect(() => {
    const start = prevRef.current
    const startTime = performance.now()

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(start + (target - start) * eased)
      if (progress < 1) rafRef.current = requestAnimationFrame(animate)
      else prevRef.current = target
    }

    rafRef.current = requestAnimationFrame(animate)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [target, duration])

  return value
}
