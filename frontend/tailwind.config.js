/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', 'sans-serif'],
      },
      colors: {
        background: '#030712', // slate-950 (Very dark)
        card: '#0f172a',      // slate-900 
        cardHover: '#1e293b', // slate-800
        primary: '#3b82f6',   // blue-500
        primaryGlow: '#60a5fa', // blue-400
        accent: '#8b5cf6',    // violet-500
        success: '#10b981',   // emerald-500
        danger: '#ef4444',    // red-500
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'glass-gradient': 'linear-gradient(145deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%)',
      },
      boxShadow: {
        'glow-primary': '0 0 20px -5px rgba(59, 130, 246, 0.5)',
        'glow-accent': '0 0 20px -5px rgba(139, 92, 246, 0.5)',
      }
    },
  },
  plugins: [],
}
