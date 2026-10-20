import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/15 disabled:pointer-events-none disabled:opacity-50", {
  variants: {
    variant: {
      default: "bg-primary text-white shadow-sm hover:bg-[#4848dc]",
      secondary: "border border-stroke bg-white text-ink hover:bg-[#f5f6fb]",
      ghost: "text-muted hover:bg-white/10 hover:text-white",
      subtle: "bg-[#efefff] text-[#5250cd] hover:bg-[#e3e3ff]",
      danger: "border border-[#f9d8de] bg-white text-[#c5304a] hover:bg-[#fff3f5]",
    },
    size: { default: "h-10 px-4 py-2", sm: "h-9 px-3", lg: "h-12 px-5", icon: "h-10 w-10" },
  },
  defaultVariants: { variant: "default", size: "default" },
});

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button({ className, variant, size, asChild = false, ...props }, ref) {
  const Comp = asChild ? Slot : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />;
});
