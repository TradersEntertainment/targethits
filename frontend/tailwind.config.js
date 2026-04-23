/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0D17', // Very dark blue/black
        card: '#15192B',      // Slightly lighter card bg
        primary: '#3B82F6',   // Blue
        accent: '#8B5CF6',    // Purple accent
        success: '#10B981',   // Green
        danger: '#EF4444',    // Red
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      }
    },
  },
  plugins: [],
}
