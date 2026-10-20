import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn("h-11 w-full rounded-xl border border-stroke bg-white px-3.5 text-sm text-ink outline-none placeholder:text-[#a5adbf] focus:border-primary focus:ring-4 focus:ring-primary/10 disabled:opacity-50", className)} {...props} />;
});

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("w-full rounded-xl border border-stroke bg-white p-3.5 text-sm text-ink outline-none placeholder:text-[#a5adbf] focus:border-primary focus:ring-4 focus:ring-primary/10", className)} {...props} />;
}
