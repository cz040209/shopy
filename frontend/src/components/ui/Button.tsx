import React from "react";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger" | "cyan";
  size?: "sm" | "md" | "lg";
  fullWidth?: boolean;
};

export default function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  children,
  ...props
}: ButtonProps) {
  const base = [
    "relative inline-flex items-center justify-center gap-2 overflow-hidden",
    "font-semibold tracking-[0.08em] uppercase text-[0.72rem]",
    "rounded-lg transition-all duration-300",
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50",
    "disabled:opacity-40 disabled:cursor-not-allowed",
    "before:absolute before:inset-0 before:origin-center before:scale-0 before:rounded-full",
    "before:bg-white/10 before:transition-transform before:duration-500",
    "hover:before:scale-150",
    fullWidth ? "w-full" : "",
  ].join(" ");

  const sizes: Record<string, string> = {
    sm: "px-5 py-2.5",
    md: "px-6 py-3",
    lg: "px-8 py-4 text-[0.76rem]",
  };

  const variants: Record<string, string> = {
    primary:
      "bg-white text-black hover:bg-cyan-400 hover:shadow-[0_0_24px_rgba(0,212,255,0.35)]",
    outline:
      "bg-transparent text-white hover:text-cyan-400 hover:shadow-[0_0_16px_rgba(0,212,255,0.15)]",
    ghost:
      "bg-transparent text-[#8892a4] border-transparent hover:text-cyan-400",
    danger:
      "bg-transparent text-red-400 border-red-400/30 hover:bg-red-500/10 hover:border-red-400",
    cyan:
      "bg-cyan-400/10 text-cyan-400 hover:bg-cyan-400/20",
  };

  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      {...props}
    >
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </button>
  );
}
