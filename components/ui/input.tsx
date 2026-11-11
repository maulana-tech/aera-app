import * as React from "react"
import { cn } from "cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-lg border border-input bg-white px-3 py-1 text-base text-fg transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground/80 hover:border-[rgba(6,35,89,0.28)] focus-visible:border-[rgba(6,71,179,0.55)] focus-visible:ring-3 focus-visible:ring-[rgba(6,71,179,0.08)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-raised disabled:opacity-60 aria-invalid:border-destructive md:text-[13.5px]",
        className
      )}
      {...props}
    />
  )
}

export { Input }
