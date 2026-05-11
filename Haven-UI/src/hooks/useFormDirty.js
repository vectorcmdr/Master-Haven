// Wizard v1 (May 2026): track form dirty state for the beforeunload guard
// and Submit Another reset preservation.
//
// Caller passes a `state` object and an optional `pristine` reference.
// Returns `{ isDirty, markClean, markDirty }`. The hook also wires up a
// beforeunload listener that fires only when isDirty is true.

import { useEffect, useRef, useState, useCallback } from 'react'

export default function useFormDirty(state, pristineRef = null) {
  const [isDirty, setIsDirty] = useState(false)
  const baselineRef = useRef(pristineRef ?? state)
  const stateRef = useRef(state)
  stateRef.current = state

  // Whenever state changes, compare to baseline. Cheap shallow check via
  // JSON stringify is fine for the wizard's snapshot size (<10 KB).
  useEffect(() => {
    try {
      const a = JSON.stringify(baselineRef.current)
      const b = JSON.stringify(state)
      setIsDirty(a !== b)
    } catch {
      setIsDirty(true)
    }
  }, [state])

  // beforeunload guard
  useEffect(() => {
    function handler(e) {
      if (!isDirty) return undefined
      e.preventDefault()
      e.returnValue = ''
      return ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  const markClean = useCallback(() => {
    baselineRef.current = stateRef.current
    setIsDirty(false)
  }, [])

  const markDirty = useCallback(() => setIsDirty(true), [])

  return { isDirty, markClean, markDirty }
}
