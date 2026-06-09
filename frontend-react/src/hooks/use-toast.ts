import * as React from "react"

interface ToastState {
  id: string
  title?: string
  description?: string
  variant?: "default" | "destructive"
}

type ToastAction =
  | { type: "ADD"; toast: ToastState }
  | { type: "REMOVE"; id: string }

let count = 0
const listeners: Array<(state: ToastState[]) => void> = []
let toasts: ToastState[] = []

function dispatch(action: ToastAction) {
  switch (action.type) {
    case "ADD":
      toasts = [...toasts, action.toast]
      break
    case "REMOVE":
      toasts = toasts.filter((t) => t.id !== action.id)
      break
  }
  listeners.forEach((l) => l(toasts))
}

export function toast(props: Omit<ToastState, "id">) {
  const id = String(++count)
  dispatch({ type: "ADD", toast: { id, ...props } })
  setTimeout(() => dispatch({ type: "REMOVE", id }), 4000)
}

export function useToast() {
  const [state, setState] = React.useState<ToastState[]>(toasts)
  React.useEffect(() => {
    listeners.push(setState)
    return () => {
      const idx = listeners.indexOf(setState)
      if (idx > -1) listeners.splice(idx, 1)
    }
  }, [])
  return { toasts: state, toast }
}
