import { Geist, Geist_Mono } from "next/font/google";

export const appFont = Geist({ subsets: ["latin"], variable: "--font-app", display: "swap" });
export const codeFont = Geist_Mono({ subsets: ["latin"], variable: "--font-code", display: "swap" });
